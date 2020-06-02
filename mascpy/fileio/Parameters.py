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



import os
import glob
import FileNameSchema as fns
from datatypes.Enums import EnumTimeParts

class AcquisitionParams(object):
    """ Specifies all of the parameters used to capture MASC data. This is basically things
        like data and image file names. These are used to parse through data to generate a list of
        paths to data / image output files for parsing. Optionally given data range

        -- Specifying data ranges --
        The range is specified as a dictionary {'from': <data>, 'to': <data>}, where <data> is
        in dictionary format {'year': 2015, 'month': 8, 'day': 5, etc} - see FileNameSchema.py
        for more details.

        One tricky thing is that data we need may spill over the time range boundary by 1 when
        collected. For ex: consider schema: data/masc_hr_%h/ which puts data into the hour when it was
        captured. If a snowflake was captured at 11:59 with two images at 11:59 and 12:00, then
        the data will lie in dataInfo.txt file within data/masc_hr_11. The first image will be placed
        within data/masc_hr_11 and its info will be within dataInfo.txt in the same folder. However,
        the image (and its data) will be written to data/masc_hr_12. We have to pull out both folders
        just to make sure the data we need lies there.

        For processing data, we really need to iterate over snowflake data (rather than image data) to build
        a table of captured snowflakes. For this, no boundary padding is necessary. However, reconstructing
        which images belong to the snowflake, we must pad the boundary and read those extra image info files
    """

    def __init__(self,
                 rootDirectory,
                 dataSubdirectorySchema,
                 dataInfoFileSearchName,
                 imageInfoFileSearchName,
                 acquisitionConfigFileSearchName):
        """ Initializes the parameters object corresponding to how the MASC was set up.
            These parameters will be used to parse MASC output directories and find / filter
            data. Must be correct!

            :param rootDirectory:
                Root directory which houses all folders and data. This directory
                will be searched recursively to find data and image output (txt) files.
                For example: /some/nfs/path/

            :param dataSubdirectorySchema:
                Subdirectory within root where all of our data is stored. Various versions of
                MASC acquisition software specify this differently. By default, we will assume
                the following schema to be used when specifying time window for processing.
                Schema:
                   masc_%d_Hr_%h
                   +%d  date (yyyy.mm.dd)       %Y - year, %M - month,  %D - day
                   +%T  time (hh.mm.ss)         %h - hour, %m - minute, %s - second
                For example:
                   masc_%d_Hr_%h     -> masc_2015.06.03_Hr_19
                   day_%d/masc_Hr_%h -> day_2015.06.03/masc_Hr_19

            :param dataInfoFileSearchName:
                Searchable string with wildflags to identify a file as data info file. By default
                these files are located within data subdirectories. Final names could include some
                part of the date when they were generated - use * to identify that portion of the
                file name.
                For example:
                  output file                         dataInfoFileSearchName value
                --------------------------------------------------------------------------------
                  ./dataInfo.txt                      dataInfo.txt
                  ./Folder_Hr_20/dataInfo.txt         dataInfo.txt -- search will be recursive
                  ./Folder_Hr_20/dataInfo_hr_20.txt   dataInfo*.txt

            :param imageInfoFileSearchName:
                Searchable string with wildflags to identify a file as image info file. Follows
                the same set of identification rules as dataInfoFileSearchName above

            :param acquisitionConfigFileSearchName:
                Searchable string with wildflags to identify a file as acquisition configuration file. Follows
                the same set of identification rules as dataInfoFileSearchName above
        """
        # used only when setting up this object for a copy later on
        if rootDirectory is None:
            return

        # base parameters
        self._rootDirectory           = rootDirectory
        self._dataSubdirectory        = dataSubdirectorySchema
        self._dataInfoFileSearchName  = dataInfoFileSearchName
        self._imageInfoFileSearchName = imageInfoFileSearchName
        self._acqConfigFileSearchName = acquisitionConfigFileSearchName
        self._imageFileSearchName     = '*.png'
        self._dataRange               = None

        # Recursion depth for subdirectories where data will be stored. This is derived
        # from dataSubdirectory specification above. We need to go to this level to find data.
        # However, output text files may be located elsewhere. For now restricted to
        # lie within root or at any recursive depth up to subdirectoryDepth
        self._subdirectoryDepth = 0

        # A small optimization which records the subdirectories valid within given date range
        # so that we don't read from the disk more than necessary
        self._foundSubdirectories = None

        # find out maximum recursion depth level of data subdirectories within root folder.
        normSubdir = self._dataSubdirectory.replace('\\/', '\\')
        for d in normSubdir.split('\\'):
            if not d == '':
                self._subdirectoryDepth += 1
        self._subdirectoryDepth = max(self._subdirectoryDepth - 1, 0)

        # create schemas for parsing things
        # subdirectories
        self._subdirSchema = fns.FileNameSchema(self._dataSubdirectory)

        # image output files
        self._imageInfoSchema = None
        if '%' in self._imageFileSearchName:
            self._imageInfoSchema = fns.FileNameSchema(self._imageFileSearchName)

        # data output files
        self._dataInfoSchema = None
        if  '%' in self._dataInfoFileSearchName:
            self._dataInfoSchema = fns.FileNameSchema(self._dataInfoFileSearchName)

        # config files
        self._acqConfigSchema = None
        if '%' in self._acqConfigFileSearchName:
            self._acqConfigSchema = fns.FileNameSchema(self._acqConfigFileSearchName)


    def SetDataRange(self, newDataRange = None):
        """ Updaets the internal data range which is used to cull any found data

            :param dataRange: tuple of dicts each specifying date / time. [from, to]
        """
        self._dataRange = newDataRange


    def Print(self):
        """ Basic print for this object
        """
        print '- root directory:             \"{0}\"'.format(self._rootDirectory)
        print '- subdirectory schema:        \"{0}\"'.format(self._dataSubdirectory)
        self._subdirSchema.Print("    ")
        print '- data range [from, to]:      {0}'    .format(self._dataRange)
        print '- max recursive depth:        {0}'    .format(self._subdirectoryDepth)
        print '- data filename schema:       \"{0}\"'.format(self._dataInfoFileSearchName)
        print '- image filename schema:      \"{0}\"'.format(self._imageInfoFileSearchName)
        print '- acq config filename schema: \"{0}\"'.format(self._acqConfigFileSearchName)


    def Copy(self, otherParams):
        """ Copies all settings from a given object of AcquisitionParams() type. This copy ignores caches
            foundSubdirectories for thread safety

            :param otherParams: object to copy from
        """
        # base parameters
        self._rootDirectory           = otherParams._rootDirectory
        self._dataSubdirectory        = otherParams._dataSubdirectory
        self._dataInfoFileSearchName  = otherParams._dataInfoFileSearchName
        self._imageInfoFileSearchName = otherParams._imageInfoFileSearchName
        self._imageFileSearchName     = otherParams._imageFileSearchName
        self._acqConfigFileSearchName = otherParams._acqConfigFileSearchName
        self._dataRange               = otherParams._dataRange
        self._subdirectoryDepth       = otherParams._subdirectoryDepth
        self._subdirSchema            = otherParams._subdirSchema
        self._imageInfoSchema         = otherParams._imageInfoSchema
        self._dataInfoSchema          = otherParams._dataInfoSchema
        self._acqConfigSchema         = otherParams._acqConfigSchema

        # A small optimization which records the subdirectories valid within given date range
        # so that we don't read from the disk more than necessary
        self._foundSubdirectories = None


    def ClearDirectoryCache(self):
        """ Clears the directory cache from the last call
        """
        self._foundSubdirectories = None


    def GetDataFolders(self, pathToSearch = None):
        """ Retrieves all data folders within root directory using a recursive search using the
            specified subdirectory naming scheme. This search block to a time range, if provided.
            If not (given as None), then we read in the entire folder. See the note above on how
            to specify data ranges.

            :param pathToSearch: directory to find data files within. If None, searches within root
            :return: list of paths to directories
        """
        dirToSearch = pathToSearch
        if dirToSearch is None:
            dirToSearch = self._rootDirectory

        # check folder exists
        if not os.path.exists(dirToSearch):
            return None

        dirFound = self._GetSubdirectoryHelper(dirToSearch, 0, self._dataRange)
        if len(dirFound) == 0:
            return None
        return dirFound


    def GetDataInfoFiles(self, pathToSearch = None):
        """ Retrieves all data files within root directory using a recursive search and
            the specified data info name. This search blocks to a time range, if provided.
            If not (given as None), then we read in the entire folder. See the note above on how
            to specify data ranges.

            :param pathToSearch: directory to find data files within. If None, searches within root
            :return: list of paths to data files
        """
        dirToSearch = pathToSearch
        if dirToSearch is None:
            dirToSearch = self._rootDirectory

        # check folder exists
        if not os.path.exists(dirToSearch):
            return None

        # If file name schema needs decoding, we'll glob with file extension, and only add files that fit the schema
        nameToGlobWith = self._dataInfoFileSearchName
        if self._dataInfoSchema is not None:
            nameToGlobWith = '*{0}'.format(os.path.splitext(os.path.basename(self._dataInfoFileSearchName))[1])

        return self._GetFilesInSubdirectoryHelper(dirToSearch,
                                                  nameToGlobWith,
                                                  self._dataInfoSchema,
                                                  self._dataRange)


    def GetImageInfoFiles(self, pathToSearch = None):
        """ Similar to GetDataInfoFiles(...) retrieves all image info files within root directory
            using a recursive search and the specified image info name.

            :param pathToSearch: directory to find image files within. If None, searches within root
            :return: list of paths to image info files or None
        """
        dirToSearch = pathToSearch
        if dirToSearch is None:
            dirToSearch = self._rootDirectory

        # check folder exists
        if not os.path.exists(dirToSearch):
            return None

        # If file name schema needs decoding, we'll glob with file extension, and only add files that fit the schema
        nameToGlobWith = self._imageInfoFileSearchName
        if self._imageInfoSchema is not None:
            nameToGlobWith = '*{0}'.format(os.path.splitext(os.path.basename(self._imageInfoFileSearchName))[1])

        return self._GetFilesInSubdirectoryHelper(dirToSearch,
                                                  nameToGlobWith,
                                                  self._imageInfoSchema,
                                                  self._dataRange)


    def GetImageFiles(self, pathToSearch = None):
        """ Similar to GetDataInfoFiles(...) retrieves all image files within root directory
            using a recursive search and the specified image extension.

            :param pathToSearch: directory to find images within. If None, searches within root
            :return: list of paths to images or None
        """
        dirToSearch = pathToSearch
        if dirToSearch is None:
            dirToSearch = self._rootDirectory

        # check folder exists
        if not os.path.exists(dirToSearch):
            return None

        return self._GetFilesInSubdirectoryHelper(dirToSearch,
                                                  self._imageFileSearchName,
                                                  None,
                                                  self._dataRange)


    def GetAcquisitionConfigFiles(self, pathToSearch = None):
        """ Similar to GetDataInfoFiles(...) retrieves all acquisition config files within root directory
            using a recursive search and the specified image extension.

            :param pathToSearch: directory to find images within. If None, searches within root
            :return: list of paths to config files or None
        """
        dirToSearch = pathToSearch
        if dirToSearch is None:
            dirToSearch = self._rootDirectory

        # check folder exists
        if not os.path.exists(dirToSearch):
            return None

        # If file name schema needs decoding, we'll glob with file extension, and only add files that fit the schema
        nameToGlobWith = self._acqConfigFileSearchName
        if self._acqConfigSchema is not None:
            nameToGlobWith = '*{0}'.format(os.path.splitext(os.path.basename(self._acqConfigFileSearchName))[1])

        return self._GetFilesInSubdirectoryHelper(dirToSearch,
                                                  nameToGlobWith,
                                                  self._acqConfigSchema,
                                                  self._dataRange)


    #
    # Helpers - should never be called externally
    #
    def _GetSubdirectoryHelper(self, path, curDepth = 0, dataRange = None):
        """ Searches through a directory given by a path and tries to find subdirectories which fall within
            the given data range. See note above how data ranges should be specified. This includes
            a quick optimization to short-circuit file search if it has been performed already.

            :param path:      current path within which to search
            :param curDepth:  recursion depth of the call to this function.
            :param dataRange: tuple of dicts each specifying date / time. [from, to]
            :return: list of subdirectories within data range (at current depth and below)
        """
        # Check if we have already called this function with a given dataRange
        if self._foundSubdirectories is not None and \
          (isinstance(self._foundSubdirectories, list) and len(self._foundSubdirectories) > 0 ):
#            print 'found subdir {0}'.format(self._foundSubdirectories)
            # TODO: check that dataRange was already given with prior search...
            return self._foundSubdirectories

        # check we even have the main directory
        if not os.path.exists(path) or curDepth > self._subdirectoryDepth:
            return None

        # Read the entire contents of the folder
        # TODO: this might be a bit dangerous perf-wise in terms of disk io, perhaps there's a better solution
        globStr    = os.path.join(path, '*/')
        allFolders = glob.glob(globStr)

        # Prepare data range we need to test against
        if dataRange is not None:
            rangeStart = dataRange[0]
            rangeEnd   = dataRange[1]
            if rangeStart[str] is None or rangeEnd[str] is None:
                dataRange = None

        # iterate through and see if we can find anything else within.
        pathsOut = []
        for f in allFolders:
            # TODO: a more scalable solution is to iterate over folders as we look them up

            # Check that path fits within given date/time range. Assume trickiness with data lying on the boundary
            # trickiness has been resolved on input
            relPath   = os.path.relpath(f, self._rootDirectory)
            dataStamp = self._subdirSchema.Decode(relPath)
#            print relPath
#            print dataStamp

            skipFolder = True

            # skip folders that could not decode using our scheme
            if dataStamp is not None: # and dataStamp[EnumTimeParts.HOUR] is not None:
                skipFolder = False

            # try to check whether data is within given range
            # NOTE: we already made sure that rangeStart and rangeEnd are good
            # TODO: actually make this check using Timestamp
#            if dataRange is not None and dataRange[Enums.TimeParts.HOUR] is not None:
#                skipFolder = False
#            if dataRange is not None:
#                strToCheck = [Enums.TimeParts.YEAR,   \
#                              Enums.TimeParts.MONTH,  \
#                              Enums.TimeParts.DAY,    \
#                              Enums.TimeParts.HOUR,   \
#                              Enums.TimeParts.MINUTE, \
#                              Enums.TimeParts.SECOND]
#                for str in strToCheck:
#                    if rangeStart[str] > dataRange[str] or rangeEnd[str] < dataRange[str]:
#                        skipFolder = True
#                        break

            # Skip recursion into this subfolder if we need to
            if skipFolder:
                continue

            # Survived so far, see that this folder is added into the list of
            # folders we need to look through for data
#            print '{0}, appending dir: {1}'.format(path, f)
            pathsOut.append(f)

            # Whatever is returned should fit within dataRange
            subPaths = self._GetSubdirectoryHelper(f, curDepth + 1, dataRange)
            if subPaths is None:
                continue

            for sp in subPaths:
                pathsOut.append(sp)

        # Set the pre-computed subdirectory list appropriately
        if self._foundSubdirectories is None and curDepth == 0:
            self._foundSubdirectories = pathsOut
#            self._foundSubdirectories.append(path)

        return pathsOut


    def _GetFilesInSubdirectoryHelper(self, path, fileNameToGlob, fileNameSchema = None, dataRange = None):
        """ Searches through a given path (recursively) to find all files with a given name
            Returns a list of these files or None if none found

            :param path:           root path which to recursively search through
            :param fileNameToGlob: string with wildcards specifying file name to search for
            :param fileNameSchema: schema decoder. If None, will rely only on fileNameToGlob to find files
            :param dataRange:      tuple of dicts each specifying date / time. [from, to]
            :return: list of found files or None
        """
        # TODO: for now we'll use glob because it's easy, but we should switch to a better os.walk...

        # Get the list of all directories of interest
        dirToCheck = self._GetSubdirectoryHelper(path, 0, dataRange)
        if path not in dirToCheck:
            dirToCheck.append(path)
        if len(dirToCheck) == 0:
            return None

        # for now print what we found
#        for d in dirToCheck:
#            print "Found folder: \"{0}\"".format(d)

        # Try to find data info files within all valid directories we just found
        foundFiles = []
        foundAtLeastOne = False
        for d in dirToCheck:
            globStr  = os.path.join(d, fileNameToGlob)
            allFiles = glob.glob(globStr)

            # If needed, try to fit filename into schema
            if fileNameSchema is not None:
                for df in allFiles:
                    dfBase = os.path.basename(df)
                    if fileNameSchema.Decode(dfBase) is not None:
                        foundAtLeastOne = True
                        foundFiles.append(df)
            else:
                # otherwise, just add everything
                for df in allFiles:
                    foundAtLeastOne = True
                    foundFiles.append(df)

        if foundAtLeastOne:
            return foundFiles
        else:
            return None


def FunctionalTest():
    """ A functional test for searching subdirectories. Unfortunately it assumes some files
        exist on disk. This can (and should) be fixed later...
    """
    print "---------------------------------"
    print "Running a test on {0}".format(__file__)

    # TODO: add pass/fail tests here with correct directory subpaths
    # TODO: add more tests including nested directories:
    # 1. blah/blah/%stuffs/%stuff/blah
    # 2. blah/blah/../../%stuffs/blah -- handling relative paths
    # 3. check outside of data range tests

    # parameters
    rootDir = 'C:\\Utah\\SnowflakeGIT\\data\\'
    dataSubdir = 'masc_%d_Hr_%h\\'
    dataInfoFile = 'dataInfo*.txt'
    imageInfoFile = 'imgInfo*.txt'

    dirObj = AcquisitionParams(rootDir, dataSubdir, dataInfoFile, imageInfoFile)

    dirObj.Print()
    print "-------------\n  Data Info Files:"

    # try to parse the folder
    print dirObj.GetDataInfoFiles()

    print "-------------\n  Image Info Files:"
    print dirObj.GetImageInfoFiles()


if __name__ == '__main__':
    FunctionalTest()
