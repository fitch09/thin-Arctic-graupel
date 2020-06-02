# Copyright (c) 2015-2016, Particle Flux Analytics, Inc
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

from DataToStringConverter import DataToStringConverter

class ImageAnalysisQualityCheck(object):
    """ Helper to define the types of quality checks we can pass after analyzing each particle.
    """
    def __init__(self):
        """ Initializes all quality parameters to False
        """
        self.passedAllChecks            = False
        self.passedMinFlakeSize         = False
        self.passedIntensityRange       = False
        self.passedIntensityMax         = False
        self.passedEdgeTouch            = False
        self.passedOutOfFocusRejection  = False
        self.passedBottomLocRange       = False

    def SetToTrue(self):
        """ Initializes all quality parameters to False
        """
        self.passedAllChecks            = True
        self.passedMinFlakeSize         = True
        self.passedIntensityRange       = True
        self.passedIntensityMax         = True
        self.passedEdgeTouch            = True
        self.passedOutOfFocusRejection  = True
        self.passedBottomLocRange       = True

    def And(self, otherCheck):
        """ Combines our quality values with the quality values from the object that was passed in
            using an and

            :param otherCheck: another obkect of ImageAnalysisQualityCheck type
        """
        self.passedAllChecks            &= otherCheck.passedAllChecks
        self.passedMinFlakeSize         &= otherCheck.passedMinFlakeSize
        self.passedIntensityRange       &= otherCheck.passedIntensityRange
        self.passedIntensityMax         &= otherCheck.passedIntensityMax
        self.passedEdgeTouch            &= otherCheck.passedEdgeTouch
        self.passedOutOfFocusRejection  &= otherCheck.passedOutOfFocusRejection
        self.passedBottomLocRange       &= otherCheck.passedBottomLocRange

    def GetBitsetAsString(self):
        """ Gets the string representation of the bitset for all of the flags stored here

            :return: string with each bit represented as a 1 or 0
        """
        toReturn = ''
        allBits  = [
            self.passedMinFlakeSize,
            self.passedIntensityRange,
            self.passedIntensityMax,
            self.passedEdgeTouch,
            self.passedOutOfFocusRejection,
            self.passedBottomLocRange,
        ]
        for bit in allBits:
            if bit:
                toReturn += '1'
            else:
                toReturn += '0'
        return toReturn

    def GetString(self, stringPrepend = ""):
        """ Gets the string describing our quality

            :param stringPrepend: prepended before each print statement. Intended for spaces
            :return: string
        """
        str  = '{0} - all quality:        {1}\n'.format(stringPrepend, self.passedAllChecks)
        str += '{0} - min flake size:     {1}\n'.format(stringPrepend, self.passedMinFlakeSize)
        str += '{0} - intensity range:    {1}\n'.format(stringPrepend, self.passedIntensityRange)
        str += '{0} - intensity max:      {1}\n'.format(stringPrepend, self.passedIntensityMax)
        str += '{0} - edge touch:         {1}\n'.format(stringPrepend, self.passedEdgeTouch)
        str += '{0} - out of focus rej:   {1}\n'.format(stringPrepend, self.passedOutOfFocusRejection)
        str += '{0} - bot loc range:      {1}\n'.format(stringPrepend, self.passedBottomLocRange)
        return str


class ImageAnalysisInfo(object):
    """ Describes all the parameters that result from analysing an image. These are abstracted here because
        all this data can be aggregated together per hydrometeor from analysis of individual images.

        The following analysis parameters are recorded (see documentation or comments below for more info):
         1.  number of particles
         2.  maximum dimension
         3.  particle area
         4.  area equivalent radius
         5.  perimeter
         6.  length across particle that touches the image edge
         7.  orientation
         8.  aspect ratio
         9.  complexity
         10. cross section
         11. mean pixel intensity
         12. mean pixel intensity variability
         13. region of interest, focus
         14. region of interest, center position
         15. region of interest, half width and half height of the bounding box
         16. region of interest, location of the bottom from the top in Y
         17. flatness of the hydrometeor
    """
    # string names and data format for each column to write out. Only for raw data
    dataStringifierRaw = DataToStringConverter([
        ['passed quality check (0, 1)',      '{0:d}'],
        ['quality check bits',               '{0}'],
        ['number of particles',              '{0}'],
        ['maximum dimension (mm)',           '{0}'],
        ['particle area (mm^2)',             '{0}'],
        ['area equivalent radius (mm)',      '{0}'],
        ['perimeter (mm)',                   '{0}'],
        ['edge touch (mm)',                  '{0}'],
        ['orientation (deg)',                '{0}'],
        ['aspect ratio (min / maj)',         '{0}'],
        ['complexity',                       '{0}'],
        ['cross sectional area (mm^2)',      '{0}'],
        ['mean pixel intensity',             '{0}'],
        ['mean pixel intensity variability', '{0}'],
        ['ROI focus',                        '{0}'],
        ['ROI position X (mm)',              '{0}'],
        ['ROI position Y (mm)',              '{0}'],
        ['ROI half width (mm)',              '{0}'],
        ['ROI half height (mm)',             '{0}'],
        ['ROI bottom position Y (mm)',       '{0}'],
        ['Rain',                             '{0}'],
    ])

    # string names and data format for each column to write out. Only for averaged data
    dataStringifierAve = DataToStringConverter([
        ['number of averaged views',         '{0}'],
        ['maximum dimension (mm)',           '{0}'],
        ['particle area (mm^2)',             '{0}'],
        ['area equivalent radius (mm)',      '{0}'],
        ['perimeter (mm)',                   '{0}'],
        ['orientation (deg)',                '{0}'],
        ['aspect ratio (min / maj)',         '{0}'],
        ['complexity',                       '{0}'],
        ['cross sectional area (mm^2)',      '{0}'],
        ['mean pixel intensity',             '{0}'],
        ['mean pixel intensity variability', '{0}'],
        ['Flatness. 0 = sphere',             '{0}'],
    ])

    def __init__(self):
        """ Sets up the data to defaults, None for each
        """
        # flag whether this was computed from an average. It lets us avoid printing values that were not computed
        # using averages
        self.isBuiltFromAverage = False

        # maximum dimension along major axis (in milli-meters)
        self.maxDimensionInMM = None

        # area of the particle (in milli-meters^2)
        self.particleAreaInMM2 = None

        # area equivalent radius (in milli-meters)
        self.areaEquivalentRadiusInMM = None

        # perimeter (in milli-meters)
        self.perimeterInMM = None

        # how much of this flake touches the edge of the image (in milli-meters)
        self.edgeTouchInMM = None

        # orientation (angle in deg from horizontal to major axis)
        self.orientationInDeg = None

        # aspect ratio (dimensionless = minor / major)
        self.aspectRatioMinOverMaj = None

        # complexity / habit = showflake perimeter / circumference of equivalent circle * (1 + intensity variability)
        self.complexity = None

        # geometric cross section (in milli-meters squared)
        self.crossSectionInMM2 = None

        # mean pixel intensity of the flake, range [0, 1] = averaged over flake
        self.meanPixelIntensity = None

        # mean pixel intensity variability of the flake, range [0, 1] = averaged over flake
        self.meanPixelIntensityVariability = None

        # region of interest focus = intensity * intensity variability
        self.regOfIntFocus = None

        # position of center of region of interest (x, y tuple with (0,0) at top, left image corner) in milli-meters
        self.regOfIntPositionInMM = [None, None]

        # half width, half height of region of interest in milli-meters.
        # So left bounds is = regOfIntPositionInMM[0] - width
        self.regOfIntHalfWidthHeightInMM = [None, None]

        # position of the bottom location of region of interest (from the top) (in milli-meters)
        # This is effectively a sum of y-values of the 2 previous variables
        self.regOfIntBotLocInMM = None

        # number of objects captured in this frame
        self.numObjects = None

        # hydrometeor flatness = | ((max of aspect ratios) - (min of aspect ratios)) / (ave aspect ratios) |
        # 0 = sphere
        self.flatness = None

        # quality checks. These correspond to ImageAnalyzer._ImageFeatureQualityCheckEnum()
        # This structure can store data, but may have been rejected the particle because of some thresholds
        self.quality = ImageAnalysisQualityCheck()

        # record how many views
        self.numUsedForAverage = 0

        # flag for particle if identified as a rain drop
        self.rain_final = -1

    def GetTableString(self, delimiter):
        """ Generates a string with the data meant for output. Each element is separated by a delimiter.
            Note: dependingo n whether the data was computed using an average will influence how it is displayed
            The data is written out in the following format (each column):
              1.  number of particles
              2.  maximum dimension
              3.  particle area
              4.  area equivalent radius
              5.  perimeter
              6.  edge touch
              7.  orientation
              8.  aspect ratio
              9.  complexity
              10. cross section
              11. mean pixel intensity
              12. mean pixel intensity variability
              13. region of interest, focus
              14. region of interest, position X
              15. region of interest, position Y
              16. region of interest, half width
              17. region of interest, half height
              18. region of interest, bottom position from top, Y
              19. flatness

            :param delimiter: string delimiter separating each column
            :return: string
        """
        # this is a bit slower, but should be easier to add items to
        # NOTE: the order here has to be the same as in the self.dataStringifier
        if self.isBuiltFromAverage:
            dataToPrint = [
                self.numUsedForAverage,
                self.maxDimensionInMM,
                self.particleAreaInMM2,
                self.areaEquivalentRadiusInMM,
                self.perimeterInMM,
                self.orientationInDeg,
                self.aspectRatioMinOverMaj,
                self.complexity,
                self.crossSectionInMM2,
                self.meanPixelIntensity,
                self.meanPixelIntensityVariability,
                self.flatness,
            ]
            return self.dataStringifierAve.GetString(dataToPrint, delimiter)
        else:
            dataToPrint = [
                self.quality.passedAllChecks,
                self.quality.GetBitsetAsString(),
                self.numObjects,
                self.maxDimensionInMM,
                self.particleAreaInMM2,
                self.areaEquivalentRadiusInMM,
                self.perimeterInMM,
                self.edgeTouchInMM,
                self.orientationInDeg,
                self.aspectRatioMinOverMaj,
                self.complexity,
                self.crossSectionInMM2,
                self.meanPixelIntensity,
                self.meanPixelIntensityVariability,
                self.regOfIntFocus,
                self.regOfIntPositionInMM[0],
                self.regOfIntPositionInMM[1],
                self.regOfIntHalfWidthHeightInMM[0],
                self.regOfIntHalfWidthHeightInMM[1],
                self.regOfIntBotLocInMM,
                self.rain_final, 
            ]
            return self.dataStringifierRaw.GetString(dataToPrint, delimiter)


    def GetString(self, stringPrepend = ""):
        """ Generates a string aimed at printing this object

            :param stringPrepend: string to pre-pend for every new line
            :return: string representing the object
        """
        toRet = ""
        toRet += '{0} - max dimension:   \"{1}\" (mm)\n'         .format(stringPrepend, self.maxDimensionInMM)
        toRet += '{0} - particle area:   \"{1}\" (mm^2)\n'       .format(stringPrepend, self.particleAreaInMM2)
        toRet += '{0} - area eq radius:  \"{1}\" (mm)\n'         .format(stringPrepend, self.areaEquivalentRadiusInMM)
        toRet += '{0} - perimeter:       \"{1}\" (mm)\n'         .format(stringPrepend, self.perimeterInMM)
        toRet += '{0} - orientation:     \"{1}\" (deg)\n'        .format(stringPrepend, self.orientationInDeg)
        toRet += '{0} - aspect ratio:    \"{1}\" (min / maj)\n'  .format(stringPrepend, self.aspectRatioMinOverMaj)
        toRet += '{0} - complexity:      \"{1}\"\n'              .format(stringPrepend, self.complexity)
        toRet += '{0} - x sect area:     \"{1}\" (mm^2)\n'       .format(stringPrepend, self.crossSectionInMM2)
        toRet += '{0} - mean intensity:  \"{1}\"\n'              .format(stringPrepend, self.meanPixelIntensity)
        toRet += '{0} - mean intens var: \"{1}\"\n'              .format(stringPrepend, self.meanPixelIntensityVariability)

        # print out quantities that are for raw vs ave values only:
        if self.isBuiltFromAverage:
            toRet += '{0} - num aved views   \"{1}\"\n'          .format(stringPrepend, self.numUsedForAverage)
            toRet += '{0} - flatness:        \"{1}\"\n'          .format(stringPrepend, self.flatness)
        else:
            toRet += '{0} - edge touch:      \"{1}\" (mm)\n'     .format(stringPrepend, self.edgeTouchInMM)
            toRet += '{0} - quality passed:  \"{1}\"\n'          .format(stringPrepend, self.quality.passedAllChecks)
            toRet += '{0} - qual pass bits:  \"{1}\"\n'          .format(stringPrepend, self.quality.GetBitsetAsString())
            toRet += '{0} - roi focus:       \"{1}\"\n'          .format(stringPrepend, self.regOfIntFocus)
            toRet += '{0} - roi position:    \"{1}\" (mm)\n'     .format(stringPrepend, self.regOfIntPositionInMM)
            toRet += '{0} - roi half wth,ht  \"{1}\" (mm)\n'     .format(stringPrepend, self.regOfIntHalfWidthHeightInMM)
            toRet += '{0} - roi bot loc, ht  \"{1}\" (mm)\n'     .format(stringPrepend, self.regOfIntBotLocInMM)
            toRet += '{0} - num objects:     \"{1}\"\n'          .format(stringPrepend, self.numObjects)
        return toRet


    def Print(self, stringPrepend = ""):
        """ Simple print function

            :param stringPrepend: S
        """
        print '{0}'.format(self.GetString(stringPrepend))


    def IsGoodForAveraging(self, fromParticles = False):
        """ Checks if this analysis can be used for averaging by comparing whether any averaged values
            were set to something other than None.

            If checking whether this value (computed from particle images) can be averaged, set fromParticles to True.
            Then, average goodness will take into account flatness being not None

            :param fromParticles: flag whether averaging from images for single particle (false) or many particles (true)
            :return: Boolean flag if this analysis can be used for averaging
        """
        particleCheck = (not fromParticles) or \
                        (fromParticles and self.flatness is not None)
        return self.maxDimensionInMM               is not None and \
               self.particleAreaInMM2              is not None and \
               self.areaEquivalentRadiusInMM       is not None and \
               self.perimeterInMM                  is not None and \
               self.orientationInDeg               is not None and \
               self.aspectRatioMinOverMaj          is not None and \
               self.complexity                     is not None and \
               self.crossSectionInMM2              is not None and \
               self.meanPixelIntensity             is not None and \
               self.meanPixelIntensityVariability  is not None and \
               particleCheck                                   and \
               self.quality.passedAllChecks


    def Average(self, infos, fromParticles = False):
        """ Sets our values to the averages of data that was passed in. The data is assumed to be an array
            of ImageAnalysisInfo() objects. Input is checked for any elements being None (thus, no particles
            were found in the image). ROI variables and num objects remain None

            If values to be averaged come from particles (say to compute binning in time), then fromParticles
            flag should be set to True. Therefore, flatness parameter will be averaged rather than computed

            :param infos: array of ImageAnalysisInfo() objects to average
            :param fromParticles: flag whether averaging from images for single particle (false) or many particles (true)
        """
        # Check for extra quilifications to exlusethe images with identified rain drops based on pixel intensity and variability from averaging.
        # It is required to have at least 2 of 3 images to pass all the quality checks for each particle id.
        # The number of particles for all (at least 2 of 3) images must be same and it has to be 1.
        qc = []
        for inx, im in enumerate(infos):
            if im.quality.passedAllChecks == 1:
                qc.append(1)
            else:
                qc.append(0)

        qc_passed = []
        for inx, val in enumerate(qc): 
            if val == 1: 
                 qc_passed.append(inx)

        count = 0
        if len(qc) == 3:
            for inx, im in enumerate(infos): 
                if qc[inx] == 1 and qc[0]+qc[1]+qc[2] >= 2 and im.numObjects == 1 and im.meanPixelIntensityVariability < 0.3 and im.meanPixelIntensity < 0.3: 
                    count += 1
            if count < len(qc_passed):
                return
        else: 
            return

        # set that we're coming from average
        self.isBuiltFromAverage = True
        self.numUsedForAverage  = 0

        # just in case
        if infos is None or   \
           len(infos) == 0 or \
           not isinstance(infos[0], ImageAnalysisInfo):
            return

        # check how many non-None particles we have
        # Because statistics comes out of a large number of samples, effectively averaging over the entire set,
        # we can accept particles where at least one image is deemed "good" (rather than requiring all images)
        goodParticles = 0
        for i in infos:
            if i.IsGoodForAveraging(fromParticles):
                goodParticles += 1
        if goodParticles == 0:
            # TODO: count this occurrence?
            return

        # this particle has at least one image providing data for the average (needed for output)
        self.quality.SetToTrue()
        self.numUsedForAverage = goodParticles

        # set values to defaults to prepare for averaging
        self.maxDimensionInMM               = 0
        self.particleAreaInMM2              = 0
        self.areaEquivalentRadiusInMM       = 0
        self.perimeterInMM                  = 0
        self.orientationInDeg               = 0
        self.aspectRatioMinOverMaj          = 0
        self.complexity                     = 0
        self.crossSectionInMM2              = 0
        self.meanPixelIntensity             = 0
        self.meanPixelIntensityVariability  = 0

        aspectMin   =  10000000
        aspectMax   = -10000000
        flatnessSum = 0

        # iterate over all inputs
        for i in infos:
            if not i.IsGoodForAveraging(fromParticles):
                continue

            # we have to average only data that's good per particle
            if fromParticles:
                flatnessSum                     += i.flatness

            self.quality.And(i.quality)

            self.maxDimensionInMM               += i.maxDimensionInMM
            self.particleAreaInMM2              += i.particleAreaInMM2
            self.areaEquivalentRadiusInMM       += i.areaEquivalentRadiusInMM
            self.perimeterInMM                  += i.perimeterInMM
            self.orientationInDeg               += i.orientationInDeg
            self.aspectRatioMinOverMaj          += i.aspectRatioMinOverMaj
            self.complexity                     += i.complexity
            self.crossSectionInMM2              += i.crossSectionInMM2
            self.meanPixelIntensity             += i.meanPixelIntensity
            self.meanPixelIntensityVariability  += i.meanPixelIntensityVariability

            aspectMin = min(aspectMin, i.aspectRatioMinOverMaj)
            aspectMax = max(aspectMax, i.aspectRatioMinOverMaj)

        # now actually average stuff
        multFactor = 1. / goodParticles
        self.maxDimensionInMM               *= multFactor
        self.particleAreaInMM2              *= multFactor
        self.areaEquivalentRadiusInMM       *= multFactor
        self.perimeterInMM                  *= multFactor
        self.orientationInDeg               *= multFactor
        self.aspectRatioMinOverMaj          *= multFactor
        self.complexity                     *= multFactor
        self.crossSectionInMM2              *= multFactor
        self.meanPixelIntensity             *= multFactor
        self.meanPixelIntensityVariability  *= multFactor

        # flatness
        # when using images, compute it from scratch, which only works when we have > 1 image
        if not fromParticles:
            if goodParticles > 1:
                self.flatness = abs((aspectMax - aspectMin) / self.aspectRatioMinOverMaj)
            else:
                self.flatness = None
        # when using particle averages, average flatness like all others
        else:
            self.flatness = flatnessSum * multFactor
