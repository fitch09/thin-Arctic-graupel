# Copyright (c) 2015-2016, Particle Flux Analytics
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
# 

import argparse
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import os
import traceback
import sys
import timeit
import glob
import math
from enum import Enum, IntEnum
from multiprocessing import Pool, Lock

from fileio.Parameters import AcquisitionParams as acParam
from fileio.RawDataIngestor import RawDataIngestor
from fileio.ParallelFileWriter import ParallelFileWriter
from fileio.AnalysisOutput import AnalysisOutput

from processing.ImageAnalyzer import ImageAnalyzer
from processing.ParticleAnalyzer import ParticleAnalyzer
from processing.TimeSeriesGenerator import TimeSeriesGenerator

from datatypes.FlakeInfo import FlakeInfo
from datatypes.Enums import EnumParserColumns
from datatypes.Errors import ErrorOpenConfig, ErrorParameterValue, ErrorInputSource
from datatypes.DataAcqConfig import DataAcqConfig
from datatypes.DataAnalysisConfig import DataAnalysisConfig


flagEnableProfiling = False
if flagEnableProfiling:
    import cProfile, pstats, StringIO


#
# Multi-threaded computation helpers
#
# TODO: move all of this stuff into their own functions... Probably need to add catching for errors
def initPool(lockIn, particlesIn, imageParamsIn, configParamsIn):
    """ Thread pool initialization used for processing particles in parallel (not subfolders). Effectively saves
        references to global objects necessary for processing

        :param lockIn:         file lock for multithreading
        :param particlesIn:    list of FlakeInfo objects for all particles to be processed
        :param imageParamsIn:  JSON string specifying default image analysis parameters for processing
        :param configParamsIn: optional list of DataAcqConfig objects. Can be empty or None
    """
    global lock, particles, defaultImgAnlParams, configParams
    lock                = lockIn
    particles           = particlesIn
    defaultImgAnlParams = imageParamsIn
    configParams        = configParamsIn


def mtWorkerPerFolder(inputV):
    """ Main entry point for multiple threads each working on a data subfolder. Each thread parses its subfolder
        to find image data, etc and then analyses all particles within. It also writes output into the data
        folder with the given filename.

        To make sure we don't miss image files straddling hour boundary, each thread also scans the folders
        for prevous and next hour for images to find a match between image info and snowflake.

        :param inputV: dictionary of input data
        :return: worker id once completed or None on error
    """
    try:
        if flagEnableProfiling:
            profiler = cProfile.Profile()
            profiler.enable()

        # get at data we got
        allFolders   = inputV['folders']
        workIndex    = inputV['workId']
        fScanner     = inputV['folderScanner']
        outputInfo   = inputV['outputInfo']
        imgDebugMode = inputV['imageDebugMode']
        defParams    = DataAnalysisConfig.LoadFromJSONString(inputV['defaultParams'])

        # create image analysis object with default parameters
        analysisParams = ImageAnalyzer.Parameters()
        analysisParams.InitFromJSONDict(defParams)
        ImageAnalyzer.useDiagnosticOutput = imgDebugMode

        # Get the central folder we are really analyzing (the one with workIndex)
        # prepare removing all cropped images (only iff -sci parameter was specified)
        if analysisParams.flagSaveCroppedImages:
            midFolder = allFolders[min(max(0, workIndex), len(allFolders) - 1)]
            try:
                fileNameToSearch = '{0}*.png'.format(analysisParams.saveCroppedImagePrepend)
                fullPath         = os.path.join(midFolder, fileNameToSearch)
                cropFilesToDel   = glob.glob(os.path.join(midFolder, fileNameToSearch))
                for f in cropFilesToDel:
                    os.remove(f)
            except Exception as e:
                print 'ERROR: something went wrong trying to delete cropped images in folder: {0}'.format(midFolder)
                print '       details: {0}'.format(e)
                traceback.print_exc(file = sys.stdout)
                print '       Continuing execution...'

        # Extract folder names we will search making sure not to fall outside of allFolders range
        foldersToScan  = allFolders[max(0, workIndex - 1) : min(workIndex + 2, len(allFolders) - 1)]
        dataInfoFolder = allFolders[workIndex]
#        print "{0} -> {1}".format(workIndex, foldersToScan)

        # crate folder scanner to get image into, data info and image files for each folder above
        folderScanner = acParam(None, None, None, None, None)
        folderScanner.Copy(fScanner)

        # TODO: for now we'll skip re-scanning of the root directory, since most likely all data lives within a subdirectory

        # Get all files we need from every directory, except for data file since it's only needed for the hour
        # we need to process
        print(dataInfoFolder)
        dataFiles       = folderScanner.GetDataInfoFiles(dataInfoFolder)
        print(dataFiles)
        imageInfoFiles  = []
        imageFiles      = []
        configFiles     = []
        folderScanner.ClearDirectoryCache()
        for f in foldersToScan:
            tmpImgInfoFiles = folderScanner.GetImageInfoFiles(f)
            if tmpImgInfoFiles is not None:
                imageInfoFiles  += tmpImgInfoFiles
            tmpImgFiles     = folderScanner.GetImageFiles(f)
            if tmpImgFiles is not None:
                imageFiles      += tmpImgFiles
            tmpConfigFiles  = folderScanner.GetAcquisitionConfigFiles(f)
            if tmpConfigFiles is not None:
                configFiles     += tmpConfigFiles
            folderScanner.ClearDirectoryCache()

        if not dataFiles:
            print "ERROR: no data files were found in \"{0}\"".format(dataInfoFolder)
            return None
        if not imageInfoFiles:
            print "ERROR: no image info files were found in \"{0}\"".format(dataInfoFolder)
            return None
        if not imageFiles:
            print "ERROR: no image files were found in \"{0}\"".format(dataInfoFolder)
            return None

    #    print "{0} data files:       {1}".format(workIndex, dataFiles)
    #    print "{0} image info files: {1}".format(workIndex, imageInfoFiles)
    #    print "{0} image files:      {1}".format(workIndex, imageFiles)

        # Generate a list of hydrometeors for processing
        configList = DataAcqConfig.GetListOfConfigs(configFiles, folderScanner._acqConfigSchema)
        ingestor   = RawDataIngestor()
        particlesL = ingestor.AggregateHydrometeorData(dataFiles, imageInfoFiles, imageFiles)
        del dataFiles, imageInfoFiles, imageFiles, configFiles

        if not particlesL:
            print "ERROR: no particles were generated in \"{0}\"".format(dataInfoFolder)
            return None

        print "{0} Got {1} particles: {2}".format(workIndex, len(particlesL), dataInfoFolder)
    #    for p in particles:
    #        p.Print("  ")


        # Process particles taking acquisition configurations into account
        imgAnalyzer = ParticleAnalyzer(analysisParams)
        ProcessParticles(imgAnalyzer, particlesL, configList)

        # TODO: check if file exists, and ask user ok to overwrite vs append... -- for now let's just overwrite
        # TODO: use schema for per-hour output
        columnDelimiter = '\t'
        if outputInfo['outputTimeBinsAnalysis']:
            # First, we need to compute the bins
            binParams  = TimeSeriesGenerator.Parameters()
            binParams.InitFromJSONDict(defParams)

            binCreator = TimeSeriesGenerator(binParams)
            allBins    = binCreator.AnalyzeParticles(particlesL)

            # Then, write them out if we have something
            if allBins is not None:
                outFile       = os.path.join(dataInfoFolder, outputInfo['outputTimeBinsFile'])
                openas        = 'w'
                header        = AnalysisOutput.GetHeaderStringPerTimeBin(columnDelimiter)
                timeBinWriter = ParallelFileWriter(outFile, openas, header)
                AnalysisOutput.WriteDataPerTimeBin(allBins, timeBinWriter, 0, columnDelimiter)
                AnalysisOutput.FlushWritingToFile(timeBinWriter)

        if outputInfo['outputImageAnalysis']:
            outFile             = os.path.join(dataInfoFolder, outputInfo['outputImageFile'])
            openas              = 'w'
            header              = AnalysisOutput.GetHeaderStringPerImage(columnDelimiter)
            imageAnalysisWriter = ParallelFileWriter(outFile, openas, header)
            AnalysisOutput.WriteDataPerImage(particlesL, imageAnalysisWriter, 0, columnDelimiter)
            AnalysisOutput.FlushWritingToFile(imageAnalysisWriter)

        if outputInfo['outputParticleAnalysis']:
            outFile                = os.path.join(dataInfoFolder, outputInfo['outputParticleFile'])
            openas                 = 'w'
            header                 = AnalysisOutput.GetHeaderStringPerParticle(columnDelimiter)
            particleAnalysisWriter = ParallelFileWriter(outFile, openas, header)
            AnalysisOutput.WriteDataPerParticle(particlesL, particleAnalysisWriter, 0, columnDelimiter)
            AnalysisOutput.FlushWritingToFile(particleAnalysisWriter)

        if flagEnableProfiling:
            profiler.disable()
            s     = StringIO.StringIO()
            pstat = pstats.Stats(profiler, stream = s).sort_stats('cumulative')
            pstat.print_stats()
            print '   ----- Item {0}, Profiling output -----\n{1}\n----------'.format(workIndex, s.getvalue())

    # We decided to exit or someone pressed ctrl + c
    except (KeyboardInterrupt, SystemExit):
        return workIndex

    # badness -> print stack trace...
    # Unfortunately Pool is very finnacky on failure and thrown exceptions, so doing this here helps debugging
    except Exception as e:
        print 'ERROR: found an exception when processing item {0} ({2}): {1}'.format(workIndex, e, dataInfoFolder)
        traceback.print_exc(file = sys.stdout)

    # TODO: return problematic stuff like particles without images or images without particles (in given time bound / hour)
    finally:
        return workIndex


def mtWorkerPerParticle(inputV):
    """ Main entry point for multiple threads working on their portion of all particles
        Both particles and default image parameters have been passed in using initPool() function above when
        threads were created. Default analysis parameters may be updated based on XML files within the folder.

        :param inputV: array of input data
                    0 - work index
                    1 - number of particles to process
                    2 - flag whether to enter image debugging mode if possible
        :return: array of values [index of work at assigment, list of output particles]
    """
    workIndex       = inputV[0]
    chunkSize       = inputV[1]
    imgDebugMode    = inputV[2]
    ourParticles    = None
    try:
        # TODO: remove me
#        if workIndex > 10:
#            return

        if flagEnableProfiling:
            profiler = cProfile.Profile()
            profiler.enable()

        # create image analyzer with default parameters
        jsonDict       = DataAnalysisConfig.LoadFromJSONString(defaultImgAnlParams)
        analysisParams = ImageAnalyzer.Parameters()
        analysisParams.InitFromJSONDict(jsonDict)
        ImageAnalyzer.useDiagnosticOutput = imgDebugMode

        # get particles we need to work on
        particleRange = [workIndex * chunkSize, min((workIndex + 1)*chunkSize, len(particles))]
        ourParticles  = particles[particleRange[0] : particleRange[1]]

        # process particles taking acquisition configurations into account
        imgAnalyzer   = ParticleAnalyzer(analysisParams)
        ProcessParticles(imgAnalyzer, ourParticles, configParams)

        # Because Python doesn't like writing to files from multiple threads, we have to ask main to do this :/

        if flagEnableProfiling:
            profiler.disable()
            s     = StringIO.StringIO()
            pstat = pstats.Stats(profiler, stream = s).sort_stats('cumulative')
            pstat.print_stats()
            print '   ----- Item {0}, Profiling output -----\n{1}\n----------'.format(workIndex, s.getvalue())

    # We decided to exit or someone pressed ctrl + c
    except (KeyboardInterrupt, SystemExit):
        return None

    # badness -> print stack trace...
    # Unfortunately Pool is very finnacky on failure and thrown exceptions, so doing this here helps debugging
    except Exception as e:
        print 'ERROR: found an exception when processing item {0}: {1}'.format(workIndex, e)
        traceback.print_exc(file = sys.stdout)
        return None

    # TODO: return problematic stuff like particles without images or images without particles (in given time bound / hour)
    return [workIndex, ourParticles]


def ProcessParticles(imgAnalyzer, ourParticles, configList):
    """ Abstracted away helper function which processes an array of particles using an image analyzer object. This
        object can be updated using a configuration list based on particle and config times. This way we can respond
        to changes in acquisition-level image cropping, etc.

        :param imgAnalyzer: object of type ImageAnalyzer to analyse given data
        :param ourParticles: list of FlakeInfo objects (sorted by capture time in ascending order) to process
        :param configList: optional list of DataAcqConfig objects (sorted by time in ascending order) used to update
                           image analysis paramters as appropriate. Can be None or empty.
    """
    # Timing information
    timeStart = timeit.default_timer()
    def PrintTimingInfo(numParticles):
        """ Prints how much time was spent processing particles, and average time per particle

            :param numParticles: number of particles we processed
        """
        elapsedTime = timeit.default_timer() - timeStart
        print 'Finished processing {0} particles. Took {1} sec, {2} sec per particle'.format(numParticles,
                                                                                             elapsedTime,
                                                                                             elapsedTime / numParticles)

    # In case we've found no config files, just process things as usual
    if configList is None or \
       len(configList) == 0:
        imgAnalyzer.AnalyzeParticles(ourParticles)
        PrintTimingInfo(len(ourParticles))
        return

    # Otherwise, we have to modify analysis parameters per batch of particles affected by these
    # Process all particles captured before first config file using defaults
    firstPartId = 0
    defPartId   = ParticleAnalyzer.FindIndexBasedOnTimestamp(ourParticles, configList[0].timestamp.dateTime)
    if not defPartId is None:
        firstPartId        = defPartId + 1
        particlesToProcess = ourParticles[0 : defPartId]
        imgAnalyzer.AnalyzeParticles(particlesToProcess)

    # Find the first config that applies to our particles (the last config with time < first particle)
    if firstPartId < len(ourParticles):
        firstPartTimestamp = ourParticles[firstPartId].captureDateTime.dateTime
        firstCfgId         = DataAcqConfig.FindIndexBasedOnTimestamp(configList, firstPartTimestamp)
        partIdFrom         = firstPartId

        for cfgIndex in range(firstCfgId, len(configList)):
            # Have we processed the last of our particles?
            if partIdFrom >= len(ourParticles):
                break

            # Get pointers to current and next configs
            configCur = configList[cfgIndex]
            configNxt = None
            if cfgIndex + 1 < len(configList):
                configNxt = configList[cfgIndex + 1]

            # Get index bounds for particles which used this configuration
            if configNxt is not None:
                partIdTo = ParticleAnalyzer.FindIndexBasedOnTimestamp(ourParticles, configNxt.timestamp.dateTime)
                if partIdTo is None:
                    partIdTo = len(ourParticles) - 1
            else:
                partIdTo = len(ourParticles) - 1

            # Segment out particles to process
            particlesToProcess = ourParticles[partIdFrom : partIdTo + 1]
            partIdFrom         = partIdTo + 1

            # Update analysis parameters using the current configuration
            imgAnalyzer.UpdateFromConfig(configCur)

            # Process data
            imgAnalyzer.AnalyzeParticles(particlesToProcess)

    # Timing info
    PrintTimingInfo(len(ourParticles))



#
# Main entry point
#
class Standalone(object):
    """ Demonstrates a simple stand-alone workflow intended to be run from command line
        on an individual workstation.

        Data input options (scan the file system for raw data):
         - recursive folder scan. Intended for root folders with data residing as .../rootFolder/masc_hr_10/<data>
         - non-recursive folder scan. Intended for data folder which contains data text files. This can also be root
         - single data file. This will automatically find corresponding image files

        Found data can be limited to a specific time range

        Data output options (can be sorted by acquisition time):
         - compound output: tabulated ASCII file with a hydrometeor per row with analysis parameters of each image
         - aggregated output: tabulated ASCII file with a hydrometeor per row with aggregated analysis
                              parameters from all images

        Details to be outlined within appropriate classes stored in fileio folder.

        Running this script is easiest from the mascpy directory, with python -m analysis.Standalone. For example:
         -recdir -i some/path/to/folder/   -oi outAnalysisImages.txt
         -dir    -i some/path/to/folder    -op outAnalysisParticles.txt
         -file   -i some/path/dataInfo.txt -ob outBins.txt              -bw 5m
    """

    # TODO: should probably switch everything to throwing errors, instead of printouts...

    class DataSourceType(Enum):
        """ Helper to define data sources for processing, set it within Data source below
        """
        DS_RECURSIVE_DIRECTORY = 0
        DS_DIRECTORY           = 1
        DS_FILE                = 2
        DS_IMAGE_DEBUG         = 3

    class AnalysisOutput(IntEnum):
        """ Helper to define data analysis output. Values must be ORable
        """
        AO_NONE      = 0
        AO_IMAGES    = 1
        AO_PARTICLES = 2
        AO_BINNED    = 4


    def __init__(self):
        """ Basic initialization of the standalone application.
        """
        # flag for clarifying if everything has been already set up after parsing the command line
        # OR setting things up in another fashion
        self._isInit = False

        # for details, see bottom of ParseCommandLine() and _InitializeFromParameters()


    def ParseCommandLine(self):
        """ Initializes the object by reading the command line. We assume nothing has been set yet.
        """
        if self._isInit:
            return

        # TODO: add a configuration file to load, so we can run things easily

        # Set up the parser
        parser = argparse.ArgumentParser(description = 'Analyzes the data collected by the MASC.')

        # what type of input we can expect to process
        inGrp = parser.add_argument_group('Data source',
                                          'Source of all data for analysis. At least one option must be specified. '
                                          'Based on this selection, -i flag will need different data (directory or '
                                          'file path).')
        srcGrp = inGrp.add_mutually_exclusive_group(required = True)
        srcGrp.add_argument('-recdir',
                            action = 'store_true',
                            help   = 'Recursive directory search as data source')
        srcGrp.add_argument('-dir',
                            action = 'store_true',
                            help   = 'Single directory as data source')
        srcGrp.add_argument('-file',
                            action = 'store_true',
                            help   = 'Data file as source for data')
        srcGrp.add_argument('-imgd', '-imageDebug',
                            action = 'store_true',
                            help   = 'Debug view for an image')

        # optional data range
#        dataRngGrp = parser.add_argument_group('Data range')

        # optional specification of subfolder and data/image info file specifications
        outOptsGrp = parser.add_argument_group('Optional MASC configuration',
                                               'Aimed at specifying subdirectory schema as well as name specification '
                                               'for image and data output files (wildflags are ok)')
        outOptsGrp.add_argument('-sds', '-subdirSchema',
                                default = 'masc_%d_Hr_%h',
                                help    = 'Subdirectory schema as described by MASC configuration XML w/o trailing slashes. (default: %(default)s)')
        outOptsGrp.add_argument('-dis', '-dataInfoSchema',
                                default = 'dataInfo*.txt',
                                help    = 'Data info file schema. Default allows for names with dates. (default: %(default)s)')
        outOptsGrp.add_argument('-iis', '-imgInfoSchema',
                                default = 'imgInfo*.txt',
                                help    = 'Image info file schema. Default allows for names with dates. (default: %(default)s)')
        outOptsGrp.add_argument('-acs', '-acqConfigSchema',
                                default = 'config*.xml',
                                help    = 'Configuration XML file schema. Default allows for names with dates. (default: %(default)s)')

        # optional parameters
        parser.add_argument('-nt', '-numThreads',
                            default = 0,
                            type    = int,
                            help    = 'Number of threads to use for processing all the data at the same time.'
                                      '0 uses all available threads. (default: %(default)s)')
        parser.add_argument('-ap', '-anlParams',
                            default = 'analysis\\defImgAnlParams.json',
                            help    = 'Input JSON file describing analysis parameters to use. (default: %(default)s)')
        parser.add_argument('-sci', '-storeCroppedImages',
                            default = False,
                            action  = 'store_true',
                            help    = 'Flag whether to store cropped images of largest flakes, located next to input'
                                      'files with crop_<filename>. Will overwrite json config setting (default: %(default)s)')

        parser.add_argument('-i', '-input',
                            required = True,
                            help     = 'Path to the input source (either path or filename, depending on data source)')

        # output group
        outGrp = parser.add_argument_group('Output',
                                           'All possible output options. At least one must be specified. '
                                           'If multiple, then all will be computed at the same time. '
                                           'If -ob set, binning is specified with -bw parameter.')
        outGrp.add_argument('-oi', '-outputImages',
                            default = None,
                            help    = 'Path to output ASCII file with analysis per image')
        outGrp.add_argument('-op', '-outputParticles',
                            default = None,
                            help    = 'Path to output ASCII file with analysis aggregated per particle')
        outGrp.add_argument('-ob', '-outputBinned',
                            default = None,
                            help    = 'Path to output ASCII file with analysis binned by time. Time specified by -bw parameter')
        outGrp.add_argument('-bw', '-binWidth',
                            default = '5m',
                            help    = 'Bin width for aggregating data. Specification is #{s,m,h}. If s, number must be ' \
                                      'an integer. No longer than hour. Must divide an hour exactly. Ex: 10s, 5m, 1h, 2m24s')

        # actually parse command line and set parameters
        args = parser.parse_args()

#        print args

        if args.recdir:
            self._dataSource = self.DataSourceType.DS_RECURSIVE_DIRECTORY
        elif args.dir:
            self._dataSource = self.DataSourceType.DS_DIRECTORY
        elif args.file:
            self._dataSource = self.DataSourceType.DS_FILE
        elif args.imgd:
            self._dataSource = self.DataSourceType.DS_IMAGE_DEBUG
            ImageAnalyzer.useDiagnosticOutput = True

        self._numThreads    = args.nt
        self._inputSource   = args.i
        self._binWidthInSec = args.bw       # to be converted from a string (here) later

        self._configSubdirSchema    = args.sds
        self._configDataInfoSchema  = args.dis
        self._configImageInfoSchema = args.iis
        self._configAcqConfigSchema = args.acs

        self._defaultParamsJson     = args.ap
        self._imageAnalysisDefaults = None
        self._binningDefaults       = None
        self._saveCroppedImages     = args.sci

        self._outputAnalysis   = self.AnalysisOutput.AO_NONE
        self._outFileImages    = None
        self._outFileParticles = None
        self._outFileBinned    = None
        if args.oi is not None:
            self._outputAnalysis |= self.AnalysisOutput.AO_IMAGES
            self._outFileImages   = args.oi
        if args.op is not None:
            self._outputAnalysis  |= self.AnalysisOutput.AO_PARTICLES
            self._outFileParticles = args.op
        if args.ob is not None:
            self._outputAnalysis |= self.AnalysisOutput.AO_BINNED
            self._outFileBinned   = args.ob

        if self._outputAnalysis == self.AnalysisOutput.AO_NONE and \
           self._dataSource is not self.DataSourceType.DS_IMAGE_DEBUG:
            raise RuntimeError('output analysis type is not specified.')

        # convert parameters into what we can work with
        self._InitializeFromParameters()


    def ProcessData(self):
        """ The main processing function for this standalone data processing application. All data is input and
            output here without anything being returned.
        """
        # just in case initialization went bad
        if not self._isInit:
            raise RuntimeError('processing parameters were not initialized.')

        # Depending on how data source was specified, create folder parser appropriately
        folderToScan  = None
        folderScanner = None
        if self._dataSource == self.DataSourceType.DS_RECURSIVE_DIRECTORY:
            folderScanner = acParam(self._inputSource,
                                    self._configSubdirSchema,
                                    self._configDataInfoSchema,
                                    self._configImageInfoSchema,
                                    self._configAcqConfigSchema)

        elif self._dataSource == self.DataSourceType.DS_DIRECTORY:
            tmp           = "{0}/../".format(self._inputSource)
            folderToScan  = self._inputSource
            folderScanner = acParam(tmp,
                                    self._configSubdirSchema,
                                    self._configDataInfoSchema,
                                    self._configImageInfoSchema,
                                    self._configAcqConfigSchema)

        elif self._dataSource == self.DataSourceType.DS_FILE:
            broken        = os.path.split(self._inputSource)
            folderToScan  = broken[0]
            tmp           = "{0}/../".format(folderToScan)
            folderScanner = acParam(tmp,
                                    self._configSubdirSchema,
                                    self._configDataInfoSchema,
                                    self._configImageInfoSchema,
                                    self._configAcqConfigSchema)


        # just in case
        if folderScanner is None and \
           self._dataSource is not self.DataSourceType.DS_IMAGE_DEBUG:
            raise RuntimeError('can not initialize folder scanner for data. Please check inputs')

        # timing everything...
        timeStart = timeit.default_timer()

        # This code will scale to multiple threads in several ways:
        # 1. recursive directory search: each thread gets a full folder to process
        # 2. single directory: each thread gets own particle to process
        # 3. single data file: each thread gets own particle to process

        # First, get list of all folders we need to work on. All folders are within specified data range with
        # error of 1 hour (to handle case where some images straddle the hour, and thus folder, boundary)
        foldersToWorkOn = []
        if folderScanner is not None:
            foldersToWorkOn = folderScanner.GetDataFolders(folderToScan)
            print "------------------------"
            print foldersToWorkOn

        # initialize thread pool
#        self._numThreads = None
        if self._numThreads is 0:
            self._numThreads = None

        # get default parameter strings
        configString = DataAnalysisConfig.GetJSONString([self._imageAnalysisDefaults.GetJSONDict(),
                                                         self._binningDefaults.GetJSONDict()])

        # Create work for processing. To process a folder per thread, assign a tripplet of folders
        # but only the data in the middle one will be processed. The outside folders may contain spilled over
        # images
        workArray = None
#        if foldersToWorkOn is not None and \
#           len(foldersToWorkOn) > 4 and \
#           self._dataSource is not self.DataSourceType.DS_IMAGE_DEBUG:
        if True:
            # Set output options
            outputInfo = {
                'outputImageAnalysis':      self._outputAnalysis & self.AnalysisOutput.AO_IMAGES,
                'outputImageFile':          self._outFileImages,
                'outputParticleAnalysis':   self._outputAnalysis & self.AnalysisOutput.AO_PARTICLES,
                'outputParticleFile':       self._outFileParticles,
                'outputTimeBinsAnalysis':   self._outputAnalysis & self.AnalysisOutput.AO_BINNED,
                'outputTimeBinsFile':       self._outFileBinned,
            }

            # we also remove root directory (listed last) from working set
            workArray = [{
                    'folders'        : foldersToWorkOn,
                    'workId'         : i,
                    'folderScanner'  : folderScanner,
                    'outputInfo'     : outputInfo,
                    'defaultParams'  : configString,
                    'timeBinWidth'   : self._binningDefaults.binWidthInSec,
                    'imageDebugMode' : ImageAnalyzer.useDiagnosticOutput,
                }
                for i in range(0, len(foldersToWorkOn))
            ]

            print "-------------------------"

            # TODO: each thread to return list of images and particles assigned to it that weren't matched within the hour!

            # do the work
            threadPool = Pool(self._numThreads)
            threadPool.map(mtWorkerPerFolder, workArray, 1)
#            for retVal in threadPool.map(mtWorkerPerFolder, workArray, 1):
#                print retVal

        # otherwise, fall back to
        # single folder workload generates all images we need up front
        else:
#        elif False:
            # Are we processing a single image?
            if self._dataSource is self.DataSourceType.DS_IMAGE_DEBUG:
                flake = FlakeInfo()
                flake.SetFallspeed({
                    EnumParserColumns.FLAKE_ID: 0,
                    EnumParserColumns.DATE_STR: '01.12.2014',
                    EnumParserColumns.TIME_STR: '12:48:25.914006',
                    EnumParserColumns.FALL_SPEED: 1.0,
                })
                flake.AddImage({
                    EnumParserColumns.CAMERA_ID: 0,
                    EnumParserColumns.DATE_STR: '01.12.2014',
                    EnumParserColumns.TIME_STR: '12:48:25.914006',
                    EnumParserColumns.IMAGE_NAME_STR: self._inputSource,
                })
                particles  = [flake]
                configList = []
                ImageAnalyzer.useDiagnosticOutput = True

            # Default code path
            else:
                # Are we parsing a single file or a folder?
                if not self._dataSource == self.DataSourceType.DS_FILE:
                    dataFiles = folderScanner.GetDataInfoFiles(folderToScan)
                else:
                    dataFiles = [self._inputSource]
                if not dataFiles:
                    raise ErrorInputSource('no data tiles were found in a given path', folderToScan)

                imageInfoFiles = folderScanner.GetImageInfoFiles(folderToScan)
                if not imageInfoFiles:
                    raise ErrorInputSource('no image info files were found in a given path', folderToScan)

                imageFiles = folderScanner.GetImageFiles(folderToScan)
                if not imageFiles:
                    raise ErrorInputSource('no image files were found in a given path', folderToScan)

                configFiles = folderScanner.GetAcquisitionConfigFiles(folderToScan)
                configList  = DataAcqConfig.GetListOfConfigs(configFiles, folderScanner._acqConfigSchema)

#            print "data files: {0}".format(dataFiles)
#            print "image info files: {0}".format(imageInfoFiles)
#            print "image files: {0}".format(imageFiles)
#            print "config files: {0}".format(configFiles)

                # Generate a list of hydrometeors to be processed later
                ingestor  = RawDataIngestor()
                particles = ingestor.AggregateHydrometeorData(dataFiles, imageInfoFiles, imageFiles)


            if not particles:
                raise RuntimeError('no particles were found, please check parameters')

            print "Got {0} particles:".format(len(particles))
#            for pList in particles:
#                for p in particles[pList]:
#                    p.Print("  ")


            # Set up file output
            # TODO: check if file exists, and ask user ok to overwrite vs append... -- for now let's just overwrite
            columnDelimiter     = '\t'
            imageAnalysisWriter = None
            if self._outputAnalysis & self.AnalysisOutput.AO_IMAGES:
                openas = 'w'
                header = AnalysisOutput.GetHeaderStringPerImage(columnDelimiter)
                imageAnalysisWriter = ParallelFileWriter(self._outFileImages, openas, header)

            particleAnalysisWriter = None
            if self._outputAnalysis & self.AnalysisOutput.AO_PARTICLES:
                openas = 'w'
                header = AnalysisOutput.GetHeaderStringPerParticle(columnDelimiter)
                particleAnalysisWriter = ParallelFileWriter(self._outFileParticles, openas, header)


            # Create work
            # TODO: fixme
            chunkSize = 20
#            numChunks = 1
            numChunks = int(math.ceil(len(particles)/float(chunkSize)))
            workArray = [[i, chunkSize, ImageAnalyzer.useDiagnosticOutput] for i in range(0, numChunks)]

            # Now analyze and write out data in parallel
            lock       = Lock()
            threadPool = Pool(self._numThreads,
                              initializer = initPool,
                              initargs    = (lock, particles, configString, configList))

            # Unfortunately Python needs only 1 thread to write to the same file... weirdness
            # So we here will have to do all the writing... ug
            results = [threadPool.apply_async(mtWorkerPerParticle, [work]) for work in workArray]
            for result in results:
                ret = result.get()
                if ret is not None:
                    workIndex     = ret[0]
                    ourParticles  = ret[1]
                    # For some reason Python copies particle array and simple access via
                    # particles[particleRange[0] : particleRange[1]] returns original pre-analysis state... ug

                    # Write them out (thread safe operation)
                    if imageAnalysisWriter is not None:
                        AnalysisOutput.WriteDataPerImage(ourParticles, imageAnalysisWriter, workIndex, columnDelimiter, lock)

                    if particleAnalysisWriter is not None:
                        AnalysisOutput.WriteDataPerParticle(ourParticles, particleAnalysisWriter, workIndex, columnDelimiter, lock)

            # Flush files we were writing to
            if imageAnalysisWriter is not None:
                AnalysisOutput.FlushWritingToFile(imageAnalysisWriter)

            if particleAnalysisWriter is not None:
                AnalysisOutput.FlushWritingToFile(particleAnalysisWriter)

        # How much time did we spend processing everything?
        elapsedTime  = timeit.default_timer() - timeStart
        mins,  secs  = divmod(elapsedTime, 60)
        hours, mins  = divmod(mins,  60)
        days,  hours = divmod(hours, 24)
        print '--------------------'
        print 'Done! Took {0} sec ({1} days, {2} hours, {3} min, {4} sec)'.format(elapsedTime, days, hours, mins, secs)

        # TODO: just in case
        return


        # single flake test
        if True:
            flake = FlakeInfo()
            flake.SetFallspeed({
                EnumParserColumns.FLAKE_ID: 113323,
                EnumParserColumns.DATE_STR: '01.12.2014',
                EnumParserColumns.TIME_STR: '12:48:25.914006',
                EnumParserColumns.FALL_SPEED: 1.0,
            })
            flake.AddImage({
                EnumParserColumns.CAMERA_ID: 0,
                EnumParserColumns.DATE_STR: '01.12.2014',
                EnumParserColumns.TIME_STR: '12:48:25.914006',
                EnumParserColumns.IMAGE_NAME_STR: 'C:\\Kostya\\College\\UUtah\\Research\\snowflakes\\OpenSource\\data\\1BASE_2014.01.12_Hr_12\\2014.01.12_12.46.08_flake_113321_cam_0.png',
            })
    #        flake.AddImage({
    #            EnumParserColumns.CAMERA_ID: 1,
    #            EnumParserColumns.DATE_STR: '01.12.2014',
    #            EnumParserColumns.TIME_STR: '12:48:25.914006',
    #            EnumParserColumns.IMAGE_NAME_STR: 'C:\\Kostya\\College\\UUtah\\Research\\snowflakes\\OpenSource\\data\\1BASE_2014.01.12_Hr_12\\2014.01.12_12.48.25_flake_113323_cam_1.png',
    #        })
    #        flake.AddImage({
    #            EnumParserColumns.CAMERA_ID: 2,
    #            EnumParserColumns.DATE_STR: '01.12.2014',
    #            EnumParserColumns.TIME_STR: '12:48:25.914006',
    #            EnumParserColumns.IMAGE_NAME_STR: 'C:\\Kostya\\College\\UUtah\\Research\\snowflakes\\OpenSource\\data\\1BASE_2014.01.12_Hr_12\\2014.01.12_12.48.25_flake_113323_cam_2.png',
    #        })
#            particles = {
#                113323: [flake]
#            }
            particles = [flake]

        if not particles:
            print "ERROR: no particles were generated. Quitting"
            return

        print "Got {0} particles:".format(len(particles))
        for p in particles:
            p.Print("  ")


        # TODO: check if file exists, and ask user ok to overwrite vs append... -- for now let's just overwrite
        columnDelimiter = '\t'
        imageAnalysisWriter = None
        if self._outputAnalysis & self.AnalysisOutput.AO_IMAGES:
            openas = 'w'
            header = AnalysisOutput.GetHeaderStringPerImage(columnDelimiter)
            imageAnalysisWriter = ParallelFileWriter(self._outFileImages, openas, header)

        particleAnalysisWriter = None
        if self._outputAnalysis & self.AnalysisOutput.AO_PARTICLES:
            openas = 'w'
            header = AnalysisOutput.GetHeaderStringPerParticle(columnDelimiter)
            particleAnalysisWriter = ParallelFileWriter(self._outFileParticles, openas, header)

        # TODO: binned writer


        # Analyze all of the data bit by bit
        analysisParams = ImageAnalyzer.Parameters()
        analysisParams.cropTop = 400
        analysisParams.cropBottom = 360
        analysisParams.cropLeft = 600
        analysisParams.cropRight = 600

        analysisParams.horizFOVPerPixelInMicrons = [
                33. / 1288 * 1000,
                63. / 2448 * 1000,
                33. / 1288 * 1000
            ]

#        firstImg = particles[80592][0].imageData[1]

#        imgAnalyzer = ImageAnalyzer(analysisParams)
#        imgAnalyzer.AnalyzeImage(firstImg)
        imgAnalyzer = ParticleAnalyzer(analysisParams)
        imgAnalyzer.AnalyzeParticles(particles)

        # Write out data in the ways we need...
        # TODO: this might be too large -- so we need to test it on a huge data set
        if self._outputAnalysis & self.AnalysisOutput.AO_IMAGES:
            AnalysisOutput.WriteDataPerImage(particles, imageAnalysisWriter, 0, columnDelimiter)
            AnalysisOutput.FlushWritingToFile(imageAnalysisWriter)

        if self._outputAnalysis & self.AnalysisOutput.AO_PARTICLES:
            AnalysisOutput.WriteDataPerParticle(particles, particleAnalysisWriter, 0, columnDelimiter)
            AnalysisOutput.FlushWritingToFile(particleAnalysisWriter)


        # TODO: Report any errors that accrued


    #
    # Helper Functions
    #
    def _InitializeFromParameters(self):
        """ Actually initializes and checks that the data has been set correctly before processing. Things like
            paths, filenames, time binning and time bounds. Once all error checks pass, isInit flag is set
            appropriately.
        """
        if self._isInit:
            return

        # check input data source exists
        if not os.path.exists(self._inputSource):
            raise ErrorInputSource('input data source does not exist', self._inputSource)

        # depending on input source option, check if input path is directory or file accordingly...
        if self._dataSource == self.DataSourceType.DS_FILE or \
           self._dataSource == self.DataSourceType.DS_IMAGE_DEBUG:
            if not os.path.isfile(self._inputSource):
                raise ErrorInputSource('input data source is not a file', self._inputSource)
        elif not os.path.isdir(self._inputSource):
            raise ErrorInputSource('input data source is not a directory', self._inputSource)

        # load default analysis parameters from a JSON file
        jsonDict = DataAnalysisConfig.LoadFromJSONFile(self._defaultParamsJson)
        self._imageAnalysisDefaults = ImageAnalyzer.Parameters()
        self._imageAnalysisDefaults.InitFromJSONDict(jsonDict)
        self._imageAnalysisDefaults.flagSaveCroppedImages = self._saveCroppedImages

        self._binningDefaults = TimeSeriesGenerator.Parameters()
        self._binningDefaults.InitFromJSONDict(jsonDict)

        # convert bin width to seconds as necessary
        self._binningDefaults.InitFromTimeDescription(self._binWidthInSec)

        # If we get here, no errors were thrown
        self._isInit = True


# Basic showcase on how to use the standalone version with parsing command line arguments
if __name__ == '__main__':
    app = Standalone()
    app.ParseCommandLine()
    app.ProcessData()
