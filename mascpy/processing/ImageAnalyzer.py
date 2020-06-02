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

from enum import IntEnum
# To allow operating in flat folder structures
try:
    from datatypes.Enums import EnumParameterType
    from datatypes.Errors import ErrorParameterValue, ErrorConfigKey
    from datatypes.ImageAnalysisInfo import ImageAnalysisInfo, ImageAnalysisQualityCheck
    from datatypes.DataAnalysisConfig import DataAnalysisConfig
except ImportError:
    from Enums import EnumParameterType
    from Errors import ErrorParameterValue, ErrorConfigKey
    from ImageAnalysisInfo import ImageAnalysisInfo, ImageAnalysisQualityCheck
    from DataAnalysisConfig import DataAnalysisConfig

# Figure out if we can issue image debugging code
globalCanUsePlt = False
try:
    from matplotlib import pyplot as plt
    globalCanUsePlt = True
except ImportError:
    globalCanUsePlt = False

import numpy as np
import os
import cv2
import math
import random

# checks which OpenCV version was loaded
def GetOpenCVMajorVer():
    return int(cv2.__version__.split('.')[0])

# Temporary testing flag whether to crop our image (True) or set areas to be cropped to background color (False)
globalCropImgFlag = True


def imadjustCV(img, lowerBound, upperBound):
        def adjust(p):
            if  p <= lowerBound*255:
                p = 0
            elif p > upperBound*255:
                p = 255
            else:
                p = ((p-lowerBound*255)/(upperBound-lowerBound))
            return p
        f = np.vectorize(adjust)
        return f(img)

#def im2bwCV(img, thresh):
#    def binary(p):
#        p = 0 if p <= thresh*(255.0) else 255
#        return p
#    f = np.vectorize(binary)
#    return f(img)

class ImageAnalyzer(object):
    """ Intended to analyze an individual image, passed in as ImageInfo. Once analysis is finished,
        fills in the data field within ImageInfo object that was passed in replacing whatever was
        already stored.
    """

    # Save major version of OpenCV, since there is a difference in getting contours between 2 and 3
    openCVVer = GetOpenCVMajorVer()

    # Flag whether we should do per-image diagnostic output
    useDiagnosticOutput = False

    class _ImageFeatureTypeEnum(IntEnum):
        """ Helper to define the types of data we can return internally when analysing images.
        """
        IFT_NUM_FLAKES                  = 0
        IFT_BOUNDING_BOX                = 1
        IFT_ELLIPSE                     = 2
        IFT_FLAKE_CONTOUR_AREA          = 3
        IFT_FLAKE_CONTOUR_PERIMETER     = 4
        IFT_FLAKE_NON_BACKGROUND_AREA   = 5
        IFT_FLAKE_PARTIAL_AREA          = 6
        IFT_MAX_INTENSITY               = 7
        IFT_AVERAGE_INTENSITY           = 8
        IFT_AVERAGE_INTENSITY_RANGE     = 9     # measures pixel variability
        IFT_FOCUS                       = 10
        IFT_AREA_FOCUS                  = 11
        IFT_EDGE_TOUCH                  = 12
        IFT_BOT_LOC_FROM_TOP            = 13
        IFT_QUALITY_CHECK               = 14


    class Parameters(object):
        """ Analysis parameters to utilize during processing
        """

        def __init__(self):
            """ Initialize some default values
            """
            # amount to crop within the images we are working on (regardless if it was already cropped)
            self.cropTop    = 0
            self.cropBottom = 0
            self.cropLeft   = 0
            self.cropRight  = 0

            # threshold identifying what's background
            self.backgroundThreshold01 = 3 / 255.

            # In order to assess the flake area internal complexities are blurred with the linefill parameter.
            # This avoids small local discontinuities to make a single flake
            self.lineFill = 200         # 200 micron line (a guess for minimum flake size)

            # minimum acceptable average width for a flake (in microns)
            self.minFlakeSize = 200

            # maximum acceptable length for a flake to touch the image frame edge (in microns)
            self.maxEdgeTouchLength = 500

            # minimum acceptable maximum pixel brightness [0 1]. Darker flakes tend to be out of focus
            self.minMaxPixelIntensity01 = 0.2

            # irregularities in the background or out-of-focus images have very low internal variability
            # Threshold below specifies the minimum variability the images must have
            self.rangeIntensityThresh01 = 5 / 255.

            # flag whether to save a cropped image for the largest particle found in the image
            # When set, we crop the image and save it with filename: path\crop_<filename>
            self.flagSaveCroppedImages   = False
            self.saveCroppedImagePrepend = 'crop_'

            # flag whether to filter out of focus images
            self.flagRejectOutOfFocus = True

            # threshold is a guess for the focus reject, not a hard and fast rule
            # lower values correspond to fewer "rejects"
            self.focusThresh01 = 0.02

            # Identify a "sweet" spot where "good" triggers happen, expressible in a distance (in mm)
            # from the top of the (uncropped at capture) frame. This will be specific to each camera
            # and its alignment. An easy way to do it is just considering a histogram of BoundingBox[1]
            self.bboxBotLocThreshMax = 39
            self.bboxBotLocThreshMin = 33

            # horizontal FOV per pixel in microns per camera
            # These default to 5MP camera with 16mm lens -> 75mm FOV for entire image
            self.horizFOVPerPixelInMicrons = [
                75. / 2448 * 1000,
                75. / 2448 * 1000,
                75. / 2448 * 1000
            ]

            # per-camera crop values, as set up during capture process
            self.perCameraCropAtCapture = [
                {
                    EnumParameterType.CROP_TOP:     0,
                    EnumParameterType.CROP_BOTTOM:  0,
                    EnumParameterType.CROP_LEFT:    0,
                    EnumParameterType.CROP_RIGHT:   0,
                },
                {
                    EnumParameterType.CROP_TOP:     0,
                    EnumParameterType.CROP_BOTTOM:  0,
                    EnumParameterType.CROP_LEFT:    0,
                    EnumParameterType.CROP_RIGHT:   0,
                },
                {
                    EnumParameterType.CROP_TOP:     0,
                    EnumParameterType.CROP_BOTTOM:  0,
                    EnumParameterType.CROP_LEFT:    0,
                    EnumParameterType.CROP_RIGHT:   0,
                },
            ]


        def _CheckParameters(self):
            """ Checks whether parameters are acceptable. If not, prints appropriate error message
            """
            # check parameters that range in [0, 1]
            toCheck01 = [
                [self.backgroundThreshold01,  'backgroundThreshold01: background threshold'],
                [self.minMaxPixelIntensity01, 'minMaxPixelIntensity01: min limit for max pixel intensity'],
                [self.rangeIntensityThresh01, 'rangeIntensityThreshold01: pixel intensity variability'],
                [self.focusThresh01,          'focusThreshold01: focus threshold'],
            ]
            for tc in toCheck01:
                if tc[0] is None:
                    raise ErrorParameterValue('image analysis parameter ({0}) has value None'.format(tc[1]), None)
                elif tc[0] < 0 or tc[0] > 1:
                    raise ErrorParameterValue('image analysis parameter ({0}) is outside [0, 1] range'.format(tc[1]), tc[0])

            # check parameters that >= 0
            toCheck0 = [
                [self.cropTop,             'additionalImageCrop - top: extra image crop from top in pixels'],
                [self.cropBottom,          'additionalImageCrop - bottom: extra image crop from top in pixels'],
                [self.cropLeft,            'additionalImageCrop - left: extra image crop from top in pixels'],
                [self.cropRight,           'additionalImageCrop - right: extra image crop from top in pixels'],
                [self.lineFill,            'lineFillInMicrons: amount of dilution making flake is detected contiguously'],
                [self.minFlakeSize,        'minFlakeSizeInMicrons: min flake size in either dimension'],
                [self.maxEdgeTouchLength,  'maxEdgeTouchLengthInMicrons: max length for a flake to touch image edge'],
                [self.bboxBotLocThreshMax, 'boundingBoxThresholdInMM - bottomMax: threshold for bottom of flake bounding box'],
                [self.bboxBotLocThreshMin, 'boundingBoxThresholdInMM - bottomMin: threshold for bottom of flake bounding box'],
            ]
            for tc in toCheck0:
                if tc[0] is None:
                    raise ErrorParameterValue('image analysis parameter ({0}) has value None'.format(tc[1]), None)
                elif tc[0] < 0:
                    raise ErrorParameterValue('image analysis parameter ({0}) must be >= 0'.format(tc[1]), tc[0])

            # check per-camera stuff is >= 0
            for c in range(0, len(self.horizFOVPerPixelInMicrons)):
                if self.horizFOVPerPixelInMicrons[c] is None:
                    raise ErrorParameterValue('image analysis horizontal fov for camera ({0}) has value None'.format(c), None)
                elif self.horizFOVPerPixelInMicrons[c] <= 0:
                    raise ErrorParameterValue('image analysis horizontal fov for camera ({0}) must be >= 0'.format(c),
                                              self.horizFOVPerPixelInMicrons[c])

            keysToCheck = [
                [EnumParameterType.CROP_TOP,    'top'],
                [EnumParameterType.CROP_BOTTOM, 'bottom'],
                [EnumParameterType.CROP_LEFT,   'left'],
                [EnumParameterType.CROP_RIGHT,  'right'],
            ]
            for c in range(0, len(self.perCameraCropAtCapture)):
                pcData = self.perCameraCropAtCapture[c]
                for k in keysToCheck:
                    if pcData[k[0]] is None:
                        raise ErrorParameterValue('image analysis crop for camera ({0}) along ({1}) has value None'.format(c, k[1]), None)
                    elif pcData[k[0]] < 0:
                        raise ErrorParameterValue('image analysis crop for camera ({0}) along ({1}) must be >= 0'.format(
                                                    c, k[1]), pcData[k[0]])


        def UpdateFromConfig(self, dataAckParams):
            """ Updates parameters that depend on acquisition parameters (XML file part of acquisition).

                :param dataAckParams: Parameters of type DataAcqConfig
            """
            self.horizFOVPerPixelInMicrons = []
            self.perCameraCropAtCapture    = []
            for dpc in dataAckParams.perCamera:
                horizFOV = dpc[EnumParameterType.CAM_HORIZ_FOV_IN_UM]
                self.horizFOVPerPixelInMicrons.append(horizFOV)

                camCrops = {
                    EnumParameterType.CROP_TOP:     dpc[EnumParameterType.CROP_TOP],
                    EnumParameterType.CROP_BOTTOM:  dpc[EnumParameterType.CROP_BOTTOM],
                    EnumParameterType.CROP_LEFT:    dpc[EnumParameterType.CROP_LEFT],
                    EnumParameterType.CROP_RIGHT:   dpc[EnumParameterType.CROP_RIGHT],
                }
                self.perCameraCropAtCapture.append(camCrops)
            self._CheckParameters()


        def InitFromJSONDict(self, rootSettings):
            """ Initializes all parameters based on input dictionary, which is assumed to be generated from importing
                JSON representation (either string or a file)

                :param rootSettings: JSON dict with data
            """
            # check that we have correct dictionary
            try:
                allSettings = rootSettings['imageAnalysisParameters']
            except KeyError as e:
                raise ErrorConfigKey('image analysis parameters json has wrong root key, not \'imageAnalysisParameters\'', None)

            # double check that all keys we have within root are the same as we expect
            errStr = 'image analysis parameters json'
            allRootKeys = [
                'additionalImageCrop',
                'backgroundThreshold01',
                'lineFillInMicrons',
                'minFlakeSizeInMicrons',
                'maxEdgeTouchLengthInMicrons',
                'minMaxPixelIntensity01',
                'rangeIntensityThreshold01',
                'flagSaveCroppedImages',
                'flagRejectOutOfFocus',
                'focusThreshold01',
                'boundingBoxThresholdInMM',
                'perCamera',
            ]
            DataAnalysisConfig.KeyChecker(allSettings, allRootKeys, 'imageAnalysisParameters', errStr)

            # check nested keys
            if 'additionalImageCrop' in allSettings:
                keysToCheck = [
                    'top',
                    'bottom',
                    'left',
                    'right'
                ]
                DataAnalysisConfig.KeyChecker(allSettings['additionalImageCrop'], keysToCheck, 'additionalImageCrop', errStr)

            if 'boundingBoxThresholdInMM' in allSettings:
                keysToCheck = [
                    'bottomMin',
                    'bottomMax'
                ]
                DataAnalysisConfig.KeyChecker(allSettings['boundingBoxThresholdInMM'], keysToCheck, 'boundingBoxThresholdInMM', errStr)

            if 'perCamera' in allSettings:
                for pc in allSettings['perCamera']:
                    # first check overall keys
                    pcCheck = [
                        'horizFOVPerPixelInMM',
                        'cropAtCapture'
                    ]
                    DataAnalysisConfig.KeyChecker(pc, pcCheck, 'perCamera', errStr)

                    # check cropping
                    if 'cropAtCapture' in pc:
                        cropCheck = [
                            'top',
                            'bottom',
                            'left',
                            'right'
                        ]
                        DataAnalysisConfig.KeyChecker(pc['cropAtCapture'], cropCheck, 'cropAtCapture', errStr)

            # If we make it here without raising any errors, all keys we got fit what we expect
            # Note: some may be missing, so we'll only parse those that aren't

            if 'additionalImageCrop' in allSettings:
                addnlCrops          = allSettings['additionalImageCrop']
                if 'top'    in addnlCrops:
                    self.cropTop    = addnlCrops['top']
                if 'bottom' in addnlCrops:
                    self.cropBottom = addnlCrops['bottom']
                if 'left'   in addnlCrops:
                    self.cropLeft   = addnlCrops['left']
                if 'right'  in addnlCrops:
                    self.cropRight  = addnlCrops['right']

            if 'backgroundThreshold01'      in allSettings:
                self.backgroundThreshold01  =  allSettings['backgroundThreshold01']
            if 'lineFillInMicrons'          in allSettings:
                self.lineFill               =  allSettings['lineFillInMicrons']
            if 'minFlakeSizeInMicrons'      in allSettings:
                self.minFlakeSize           =  allSettings['minFlakeSizeInMicrons']
            if 'maxEdgeTouchLengthInMicrons' in allSettings:
                self.maxEdgeTouchLength     =  allSettings['maxEdgeTouchLengthInMicrons']
            if 'minMaxPixelIntensity01'     in allSettings:
                self.minMaxPixelIntensity01 =  allSettings['minMaxPixelIntensity01']
            if 'rangeIntensityThreshold01'  in allSettings:
                self.rangeIntensityThresh01 =  allSettings['rangeIntensityThreshold01']
            if 'flagSaveCroppedImages'      in allSettings:
                self.flagSaveCroppedImages  = (allSettings['flagSaveCroppedImages'] == 1)
            if 'flagRejectOutOfFocus'       in allSettings:
                self.flagRejectOutOfFocus   = (allSettings['flagRejectOutOfFocus'] == 1)
            if 'focusThreshold01'           in allSettings:
                self.focusThresh01          =  allSettings['focusThreshold01']

            if 'boundingBoxThresholdInMM'   in allSettings:
                bboxThresh                  =  allSettings['boundingBoxThresholdInMM']
                if 'bottomMax' in bboxThresh:
                    self.bboxBotLocThreshMax = bboxThresh['bottomMax']
                if 'bottomMin' in bboxThresh:
                    self.bboxBotLocThreshMin = bboxThresh['bottomMin']

            if 'perCamera' in allSettings:
                perCamera = allSettings['perCamera']

                # copy the last camera info if we have more cameras in allSettings than we initialized
                if len(self.horizFOVPerPixelInMicrons) < len(perCamera):
                    toAdd = len(perCamera) - len(self.horizFOVPerPixelInMicrons)
                    for i in range(toAdd):
                        self.horizFOVPerPixelInMicrons.append(self.horizFOVPerPixelInMicrons[-1])
                if len(self.perCameraCropAtCapture) < len(perCamera):
                    toAdd   = len(perCamera) - len(self.perCameraCropAtCapture)
                    copyVal = self.perCameraCropAtCapture[-1]
                    for i in range(toAdd):
                        newVal = {
                            EnumParameterType.CROP_TOP:     copyVal[EnumParameterType.CROP_TOP],
                            EnumParameterType.CROP_BOTTOM:  copyVal[EnumParameterType.CROP_BOTTOM],
                            EnumParameterType.CROP_LEFT:    copyVal[EnumParameterType.CROP_LEFT],
                            EnumParameterType.CROP_RIGHT:   copyVal[EnumParameterType.CROP_RIGHT]
                        }
                        self.perCameraCropAtCapture.append(newVal)

                for i in range(len(perCamera)):
                    pc = perCamera[i]
                    if 'horizFOVPerPixelInMM' in pc:
                        self.horizFOVPerPixelInMicrons[i] = pc['horizFOVPerPixelInMM'] * 1000.

                    # cropping
                    if 'cropAtCapture' in pc:
                        cropOpts = pc['cropAtCapture']
                        self.perCameraCropAtCapture[i][EnumParameterType.CROP_TOP]    = cropOpts['top']
                        self.perCameraCropAtCapture[i][EnumParameterType.CROP_BOTTOM] = cropOpts['bottom']
                        self.perCameraCropAtCapture[i][EnumParameterType.CROP_LEFT]   = cropOpts['left']
                        self.perCameraCropAtCapture[i][EnumParameterType.CROP_RIGHT]  = cropOpts['right']

            # Check input
            self._CheckParameters()


        def GetJSONDict(self):
            """ Generate JSON dictionary from parameter data. The dictionary returned encodes both the data
                and the key string used within JSON using 'data' and 'key' keys within.

                :return: JSON dictionary
            """
            jsonKey  = 'imageAnalysisParameters'
            jsonData = {
                'additionalImageCrop': {
                    'top':      int(self.cropTop),
                    'bottom':   int(self.cropBottom),
                    'left':     int(self.cropLeft),
                    'right':    int(self.cropRight),
                },
                'backgroundThreshold01':        float(self.backgroundThreshold01),
                'lineFillInMicrons':            float(self.lineFill),
                'minFlakeSizeInMicrons':        float(self.minFlakeSize),
                'maxEdgeTouchLengthInMicrons':  float(self.maxEdgeTouchLength),
                'minMaxPixelIntensity01':       float(self.minMaxPixelIntensity01),
                'rangeIntensityThreshold01':    float(self.rangeIntensityThresh01),
                'flagSaveCroppedImages':        int  (self.flagSaveCroppedImages),
                'flagRejectOutOfFocus':         int  (self.flagRejectOutOfFocus),
                'focusThreshold01':             float(self.focusThresh01),
                'boundingBoxThresholdInMM': {
                    'bottomMax': float(self.bboxBotLocThreshMax),
                    'bottomMin': float(self.bboxBotLocThreshMin),
                },
                'perCamera': []
            }
            for h, c in zip(self.horizFOVPerPixelInMicrons, self.perCameraCropAtCapture):
                jsonData['perCamera'].append({
                    'horizFOVPerPixelInMM': float(h / 1000.),
                    'cropAtCapture': {
                        'top':      int(c[EnumParameterType.CROP_TOP]),
                        'bottom':   int(c[EnumParameterType.CROP_BOTTOM]),
                        'left':     int(c[EnumParameterType.CROP_LEFT]),
                        'right':    int(c[EnumParameterType.CROP_RIGHT]),
                    }
                })
            return {
                'key':  jsonKey,
                'data': jsonData
            }


    def __init__(self, parameters = None):
        """ Initializes the object, by setting parameters for analysis as provided. We internally
            store the image object as loaded by OpenCV

            :param parameters: analysis parameters specified by Parameters()
        """
        # save the parameters as we need them to be or some defaults
        if parameters is None:
            self._parameters = self.Parameters()
        else:
            self._parameters = parameters

        # set up grayscale image
        self._image = None

        # camera id for this image
        self._camId = None

        # update internal variables that depend on changeable things
        self._UpdateInternals()

        # helpers
        # set up cropped image for the largest flake that was detected
        self._croppedImage = None
        self._erodedImg    = None


    def _UpdateInternals(self):
        """ Updates internal values that depend on paramters that can be updated after initialization
        """
        # prepare per camera computations
        # kernels for dilation/erosion
        kernelSize1D = [int(math.floor(1.5 * self._parameters.lineFill / x)) for x in self._parameters.horizFOVPerPixelInMicrons]
        #self._erodeFilters = [cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)) for k in kernelSize1D]

        # pre-generate filters we could use
        filtSquare  = [np.ones((k, k), np.uint8) for k in kernelSize1D]
        filtDiamond = [self._GenStructElemDiamond(k) for k in kernelSize1D]

        # we now pick which we would like to use to dilation and erosion
        choice = 1
        # use square for both dilation and erosion
        if choice is 0:
            self._dilateFilters = filtSquare
            self._erodeFilters  = filtSquare
            self._numErosion    = 1
        # use diamond for both dilation and erosion
        # (seems to produce sharper tentacles for snowflakes)
        elif choice is 1:
            self._dilateFilters = filtDiamond
            self._erodeFilters  = filtDiamond
            self._numErosion    = 1
        # use square for dilation and 2ce diamond for erosion
        elif choice is 2:
            self._dilateFilters = filtSquare
            self._erodeFilters  = filtDiamond
            self._numErosion    = 2

        # flake area threshold in pixels
        self._nonBackAreaThresh = [math.floor(math.pow(self._parameters.minFlakeSize / x, 2)) for x in self._parameters.horizFOVPerPixelInMicrons]

        # flake edge touch length (in pixels)
        self._edgeTouchThresh = [self._parameters.maxEdgeTouchLength / x for x in self._parameters.horizFOVPerPixelInMicrons]


    def _GenStructElemDiamond(self, fullWidth):
        """ Generates a structuring element in the shape of a diamond, similar to MATLAB. When the width is
            even, then there are two 1s at the edges.

            :param fullWidth: full width of the structuring element
            :return: array with the element
        """
        filled  = np.ones((fullWidth, fullWidth), np.uint8)
        width0s = int(math.floor(fullWidth / 2.))

        # What to do for even?
        if fullWidth % 2 == 0:
            width0s -= 1

        # create diamond shape with two loops
        for i in range(0, width0s):
            # now for all columns in this row
            for j in range(0, width0s - i):
                # left side. Top then bottom
                filled[     i,      j] = 0
                filled[     i, -1 - j] = 0

                # right side. Top then bottom
                filled[-1 - i,      j] = 0
                filled[-1 - i, -1 - j] = 0
        return filled


    @staticmethod
    def _HelperDrawOrSaveImage(img, title, colormap, fileName):
	if img is None:
            return
        # display as figure
        if globalCanUsePlt:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.set_title(title)
            if colormap is not None:
                ax.imshow(img, colormap)
            else:
                ax.imshow(img)
        # save the image
        else:
            fName = '{0}.png'.format(fileName)	   
            if os.path.exists(fName):
                os.remove(fName)
            cv2.imwrite(fName, img)


    def UpdateFromConfig(self, dataAckParams):
        """ Updates parameters that depend on acquisition parameters.

            :param dataAckParams: Parameters of type DataAcqConfig
        """
        self._parameters.UpdateFromConfig(dataAckParams)
        self._UpdateInternals()


    def UpdateFromJSONDict(self, newConfig):
        """ Updates parameters that depend on acquisition parameters, using JSON dictionary

            :param newConfig: JSON dictionary with new values
        """
        self._parameters.InitFromJSONDict(newConfig)
        self._UpdateInternals()


    def AnalyzeImage(self, imageInfo):
        """ Runs an analysis on a single image writing the results into the passed-in object

            :param imageInfo: object to analyze of type datatypes.ImageInfo
        """
        # check that the image file actually exists
        #print 'current file: ',imageInfo.fileName
        if not os.path.exists(imageInfo.fileName) or not os.path.isfile(imageInfo.fileName):
            return
        if imageInfo.cameraId is None:
            return

        genDebugFigure = False
        if self.useDiagnosticOutput:
            if not globalCanUsePlt:
#                raise RuntimeError('Attempting to work in image debug mode but matPlotLib was not loaded')
                print 'WARNING: matplotlib could not be loaded. Saving debug files instead...'
            genDebugFigure = True

        # open the file, convert to grayscale if needed
        self._image     = cv2.imread(imageInfo.fileName, cv2.IMREAD_GRAYSCALE)
        self._erodedImg = None

        # set up camera index for this image
        self._camId = imageInfo.cameraId

        # Prepare images for debug figure output
        self._debugNonBackMask = None
        self._debugCntImg      = None
        if genDebugFigure:
            debugImg = cv2.cvtColor(self._image, cv2.COLOR_GRAY2RGB)

            # draw cropping rectangle
            h, w, d = debugImg.shape
            cv2.rectangle(debugImg,
                          (self._parameters.cropLeft, self._parameters.cropTop),
                          (w - self._parameters.cropRight, h - self._parameters.cropBottom),
                          (0, 255, 255),
                          2)

            # draw horizontal lines for bot loc threshold
            # TODO: figure out what the correct camera id is
            convertToMM = self._parameters.horizFOVPerPixelInMicrons[self._camId] / 1000.
            pxTop       = int(math.floor(self._parameters.bboxBotLocThreshMin / convertToMM))
            pxBot       = int(math.floor(self._parameters.bboxBotLocThreshMax / convertToMM))
            cv2.line(debugImg, (0, pxTop), (w, pxTop), (255, 0, 0), 2)
            cv2.line(debugImg, (0, pxBot), (w, pxBot), (255, 0, 0), 2)

        # get features
        features = self._GetImageFeatures(genDebugFigure)

        # conversion factor
        convertToMM  = self._parameters.horizFOVPerPixelInMicrons[self._camId] / 1000.
        convertToMM2 = convertToMM * convertToMM

        # populate imageInfo object with results
        if features is not None:
            imageInfo.analysisResults.numObjects = features[self._ImageFeatureTypeEnum.IFT_NUM_FLAKES]

            # physical characteristics
            # ... partial area
            # Ellipses are defined kind of funny by OpenCV - as rotated boxes. They are specified by
            # 2D center, 2D (width, height) and rotation in degrees from horizontal in clockwise direction
            # Either width or height can be the largest.
            # Matlab's orientation is in [-90,90], while OpenCV is [0,360]
            ellipseInfo = features[self._ImageFeatureTypeEnum.IFT_ELLIPSE]
            # if width isn't largest dimension, we have to add some rotation, etc
            rotAngle = ellipseInfo[2]
            if ellipseInfo[1][0] < ellipseInfo[1][1]:
                rotAngle += 90
            if rotAngle >= 360:
                rotAngle -= 360

            # change from clockwise [0,360] to [-90,90] counterclockwise
            if rotAngle < 90:
                rotAngle = -rotAngle
            elif rotAngle < 180:
                rotAngle = 180 - rotAngle
            elif rotAngle < 270:
                rotAngle = -rotAngle + 180
            else:
                rotAngle = 360 - rotAngle
            imageInfo.analysisResults.orientationInDeg = abs(rotAngle)

            # get aspect ratio, etc
            largeDim = max(ellipseInfo[1])
            smallDim = min(ellipseInfo[1])
            imageInfo.analysisResults.maxDimensionInMM      = largeDim * convertToMM
            imageInfo.analysisResults.aspectRatioMinOverMaj = smallDim / largeDim
            imageInfo.analysisResults.crossSectionInMM2     = features[self._ImageFeatureTypeEnum.IFT_FLAKE_NON_BACKGROUND_AREA] * convertToMM2
            imageInfo.analysisResults.perimeterInMM         = features[self._ImageFeatureTypeEnum.IFT_FLAKE_CONTOUR_PERIMETER] * convertToMM
            imageInfo.analysisResults.edgeTouchInMM         = features[self._ImageFeatureTypeEnum.IFT_EDGE_TOUCH] * convertToMM
            # ... internal structure density

            # image statistics
            imageInfo.analysisResults.particleAreaInMM2             = features[self._ImageFeatureTypeEnum.IFT_FLAKE_CONTOUR_AREA] * convertToMM2
            imageInfo.analysisResults.areaEquivalentRadiusInMM      = math.sqrt(features[self._ImageFeatureTypeEnum.IFT_FLAKE_NON_BACKGROUND_AREA] / math.pi) * convertToMM
            imageInfo.analysisResults.complexity                    = imageInfo.analysisResults.perimeterInMM /                             \
                                                                      (2. * math.pi * imageInfo.analysisResults.areaEquivalentRadiusInMM) * \
                                                                      (1. + features[self._ImageFeatureTypeEnum.IFT_AVERAGE_INTENSITY_RANGE])

            imageInfo.analysisResults.meanPixelIntensity            = features[self._ImageFeatureTypeEnum.IFT_AVERAGE_INTENSITY]
            imageInfo.analysisResults.meanPixelIntensityVariability = features[self._ImageFeatureTypeEnum.IFT_AVERAGE_INTENSITY_RANGE]

            imageInfo.analysisResults.regOfIntFocus = features[self._ImageFeatureTypeEnum.IFT_AVERAGE_INTENSITY] *      \
                                                      features[self._ImageFeatureTypeEnum.IFT_AVERAGE_INTENSITY_RANGE]

            imageInfo.analysisResults.regOfIntHalfWidthHeightInMM[0] = 0.5 * features[self._ImageFeatureTypeEnum.IFT_BOUNDING_BOX][2] * convertToMM
            imageInfo.analysisResults.regOfIntHalfWidthHeightInMM[1] = 0.5 * features[self._ImageFeatureTypeEnum.IFT_BOUNDING_BOX][3] * convertToMM

            imageInfo.analysisResults.regOfIntPositionInMM[0] = features[self._ImageFeatureTypeEnum.IFT_BOUNDING_BOX][0] * convertToMM + \
                                                                imageInfo.analysisResults.regOfIntHalfWidthHeightInMM[0]
            imageInfo.analysisResults.regOfIntPositionInMM[1] = features[self._ImageFeatureTypeEnum.IFT_BOUNDING_BOX][1] * convertToMM + \
                                                                imageInfo.analysisResults.regOfIntHalfWidthHeightInMM[1]

            imageInfo.analysisResults.regOfIntBotLocInMM      = features[self._ImageFeatureTypeEnum.IFT_BOT_LOC_FROM_TOP]

            # save quality data out
            imageInfo.analysisResults.quality = features[self._ImageFeatureTypeEnum.IFT_QUALITY_CHECK]

            # if specified, crop largest particle from the image and save it
            # but only if we passed all quality checks
            if self._parameters.flagSaveCroppedImages and \
               features[self._ImageFeatureTypeEnum.IFT_QUALITY_CHECK].passedAllChecks:
                # get flake bounds
                flakeBBox = features[self._ImageFeatureTypeEnum.IFT_BOUNDING_BOX]

                # Correct bbox computation, since it may include extra crop
                if globalCropImgFlag:
                    flakeBBox[0] -= self._parameters.cropLeft
                    flakeBBox[1] -= self._parameters.cropTop

                # Actually crop
                self._croppedImage = self._image[flakeBBox[1] : flakeBBox[1] + flakeBBox[3] + 1,
                                                 flakeBBox[0] : flakeBBox[0] + flakeBBox[2] + 1]

                # get output file name
                fileLoc  = os.path.split(imageInfo.fileName)[0]
                fileBase = os.path.basename(imageInfo.fileName)
                fileOut  = os.path.join(fileLoc, '{0}{1}'.format(self._parameters.saveCroppedImagePrepend, fileBase))

                # actually write everything out
                cv2.imwrite(fileOut, self._croppedImage)

            # Draw flake bounds on the image if we're debugging it
            if genDebugFigure:
                flakeBBox = features[self._ImageFeatureTypeEnum.IFT_BOUNDING_BOX]
                cv2.rectangle(debugImg,
                              (flakeBBox[0], flakeBBox[1]),
                              (flakeBBox[0] + flakeBBox[2], flakeBBox[1] + flakeBBox[3]),
                              (0, 255, 0),
                              2)

        # Debug images figure
        if genDebugFigure:
            self._HelperDrawOrSaveImage(debugImg,               os.path.basename(imageInfo.fileName),     None,   'DEBUG_1_original')
            self._HelperDrawOrSaveImage(self._erodedImg,        'Eroded (after crop)',                    'gray', 'DEBUG_2_eroded')
            self._HelperDrawOrSaveImage(self._debugCntImg,      'All contours (after crop)',              None,   'DEBUG_3_contours')
            self._HelperDrawOrSaveImage(self._debugNonBackMask, 'All non-background pixels (after crop)', 'gray', 'DEBUG_4_nonBackgroundMask')

            # print winning values after we passed (or not)
            print 'Image analysis results'
            imageInfo.analysisResults.Print()

            if globalCanUsePlt:
                plt.show()

            del debugImg
            del self._debugCntImg
            del self._debugNonBackMask

        # clean up
        del self._image
        del self._croppedImage
        del self._erodedImg
        self._image        = None
        self._erodedImg    = None
        self._croppedImage = None


    #
    # Helper functions
    #
    def _GetImageFeatures(self, genDebugFigure = False):
        """ Actually computes all of the image parameters and returns a dictionary with them

            :return: dictionary containing analysis, key is ImageFeatureTypeEnum
        """
        # sanitize the image first to remove background noise
        self._MaskOutBackground()

        # mark up all parts of the image that will be of interest

        self._CreateAdjustImage(genDebugFigure)
#        self._CreateSobelImage(genDebugFigure)
#        self._CreateOtsuImage(genDebugFigure)

        # prepare for output
        numGoodFlakes        = 0
        maxGoodFlakeFocus    = -1
        maxAnyFlakeFocus     = -1
        dataInGoodFocusFlake = None
        dataInAnyFocusFlake  = None

        # pre-compute images used to analyze each contour
        background255 = self._parameters.backgroundThreshold01 * 255.
        nonBackMask   = cv2.compare(self._image, background255, cv2.CMP_GT)

        eKernel    = np.ones((3,3),np.uint8)
        imgEroded  = cv2.erode (self._image, eKernel, iterations = 1)
        imgDilated = cv2.dilate(self._image, eKernel, iterations = 1)
        imgIntensityRange = abs(imgDilated - imgEroded)
        del imgEroded, imgDilated

        # Create a mask for image border, taking additional cropping per image into account
        borderPixels = np.zeros(self._image.shape, dtype = np.uint8)
        if globalCropImgFlag:
            borderPixels[ 0,  :] = 255
            borderPixels[-1,  :] = 255
            borderPixels[ :,  0] = 255
            borderPixels[ :, -1] = 255
        else:
            borderPixels[ self._parameters.cropTop,        :] = 255
            borderPixels[-self._parameters.cropBottom - 1, :] = 255
            borderPixels[ :,  self._parameters.cropLeft     ] = 255
            borderPixels[ :, -self._parameters.cropRight - 1] = 255

        convertToMM = self._parameters.horizFOVPerPixelInMicrons[self._camId] / 1000.

        # iterate over all parts of flakes in this image
        if ImageAnalyzer.openCVVer == 3:
            (_, contours, _) = cv2.findContours(self._erodedImg, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        else:
            (contours, _) = cv2.findContours(self._erodedImg, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        maskImg = np.zeros(self._image.shape, np.uint8)

        # Debug -- draw all image contours together
        if self.useDiagnosticOutput: # and globalCanUsePlt:
            print 'num contours: {0}'.format(len(contours))
            w, h              = self._image.shape
            self._debugCntImg = np.zeros((w, h, 3), np.uint8)
            if globalCanUsePlt:
                colors        = plt.cm.rainbow(np.linspace(0, 1, 10))
            else:
                colors        = [(random.random(), random.random(), random.random()) for i in range(10)]
            for i in range(len(contours)):
                # thickness -1 = filled, # = thickness
                color01 = colors[i % len(colors)]
                color   = [255. * v for v in color01]
                cv2.drawContours(self._debugCntImg, contours, i, color, -1)
            self._debugNonBackMask = nonBackMask

        # Process each contour
        for i in range(0, len(contours)):
            # generate mask for the image
            if len(contours[i]) < 0:
                continue
            maskImg.fill(0)
            cv2.drawContours(maskImg, contours, i, 255, -1)

            # analyze part of the image within the mask
            dataPerContour = self._AnalyzeContour(contours[i], maskImg, nonBackMask, imgIntensityRange, borderPixels) 
            if dataPerContour is None:
                continue

            # compute distance of bottom of flake from top of the frame (in mm)
            # computed as: (top_loc + height) * conversion_into_mm
            partBotLocFromTopInMM = (dataPerContour[self._ImageFeatureTypeEnum.IFT_BOUNDING_BOX][1] +
                                     dataPerContour[self._ImageFeatureTypeEnum.IFT_BOUNDING_BOX][3]) * convertToMM
            dataPerContour[self._ImageFeatureTypeEnum.IFT_BOT_LOC_FROM_TOP] = partBotLocFromTopInMM

            # apply filter to make sure this is a "good" flake
            passMinFlakeSize   = dataPerContour[self._ImageFeatureTypeEnum.IFT_FLAKE_NON_BACKGROUND_AREA] > self._nonBackAreaThresh[self._camId]
            passIntensityRange = dataPerContour[self._ImageFeatureTypeEnum.IFT_AVERAGE_INTENSITY_RANGE] >= self._parameters.rangeIntensityThresh01
            passIntensityMax   = dataPerContour[self._ImageFeatureTypeEnum.IFT_MAX_INTENSITY] >= self._parameters.minMaxPixelIntensity01
            passEdgeTouch      = dataPerContour[self._ImageFeatureTypeEnum.IFT_EDGE_TOUCH] <= self._edgeTouchThresh[self._camId]
            passRejectFocus    = (not self._parameters.flagRejectOutOfFocus or
                                  (self._parameters.flagRejectOutOfFocus and
                                   round(dataPerContour[self._ImageFeatureTypeEnum.IFT_FOCUS]*100)/100. >= self._parameters.focusThresh01))
            passBotLocRange    = (partBotLocFromTopInMM >= self._parameters.bboxBotLocThreshMin) and \
                                 (partBotLocFromTopInMM <= self._parameters.bboxBotLocThreshMax)

            qualityCheck                            = ImageAnalysisQualityCheck()
            qualityCheck.passedMinFlakeSize         = passMinFlakeSize
            qualityCheck.passedIntensityRange       = passIntensityRange
            qualityCheck.passedIntensityMax         = passIntensityMax
            qualityCheck.passedEdgeTouch            = passEdgeTouch
            qualityCheck.passedOutOfFocusRejection  = passRejectFocus
            qualityCheck.passedBottomLocRange       = passBotLocRange

            # Record info for the most in focus flake, including filter passes
            if maxAnyFlakeFocus < dataPerContour[self._ImageFeatureTypeEnum.IFT_AREA_FOCUS]:
                maxAnyFlakeFocus             = dataPerContour[self._ImageFeatureTypeEnum.IFT_AREA_FOCUS]
                dataInAnyFocusFlake          = dataPerContour
                qualityCheck.passedAllChecks = False
                dataInAnyFocusFlake[self._ImageFeatureTypeEnum.IFT_QUALITY_CHECK] = qualityCheck

            # Count number of flakes that pass all filters above
            if passMinFlakeSize     and \
               passIntensityRange   and \
               passIntensityMax     and \
               passEdgeTouch        and \
               passRejectFocus      and \
               passBotLocRange:
                numGoodFlakes += 1

                # Record "good" flake info
                if maxGoodFlakeFocus < dataPerContour[self._ImageFeatureTypeEnum.IFT_AREA_FOCUS]:
                    maxGoodFlakeFocus            = dataPerContour[self._ImageFeatureTypeEnum.IFT_AREA_FOCUS]
                    dataInGoodFocusFlake         = dataPerContour
                    qualityCheck.passedAllChecks = True
                    dataInGoodFocusFlake[self._ImageFeatureTypeEnum.IFT_QUALITY_CHECK] = qualityCheck

        # We're done
        del nonBackMask, imgIntensityRange, borderPixels, maskImg
        if numGoodFlakes > 0:
            # TODO: add check on realreafocus < velthresh
            dataInGoodFocusFlake[self._ImageFeatureTypeEnum.IFT_NUM_FLAKES] = numGoodFlakes
            return dataInGoodFocusFlake
        else:
            if dataInAnyFocusFlake is not None:
                dataInAnyFocusFlake[self._ImageFeatureTypeEnum.IFT_NUM_FLAKES] = 0
            return dataInAnyFocusFlake


    def _MaskOutBackground(self):
        """ Uses a background threshold to clean up noise. This aids contouring and such
        """
        background255 = self._parameters.backgroundThreshold01 * 255.

        # set areas within "crop" to background noise, but only if we have enough pixels in the image
        # Actually crop the image (if we can)
        imgH, imgW = self._image.shape[:2]
        if globalCropImgFlag and \
           ((0 < self._parameters.cropTop  + self._parameters.cropBottom < imgH) or
            (0 < self._parameters.cropLeft + self._parameters.cropRight  < imgW)):
            croppedImg = self._image[self._parameters.cropTop  : imgH - self._parameters.cropBottom,
                                     self._parameters.cropLeft : imgW - self._parameters.cropRight]
            del self._image
            self._image = croppedImg
        # Just color areas to be cropped a background color
        else:
            if 0 < self._parameters.cropTop < imgH:
                self._image[0:self._parameters.cropTop, :]    = background255
            if 0 < self._parameters.cropBottom < imgH:
                self._image[-self._parameters.cropBottom:, :] = background255
            if 0 < self._parameters.cropLeft < imgW:
                self._image[:, 0:self._parameters.cropLeft]   = background255
            if 0 < self._parameters.cropRight < imgW:
                self._image[:, -self._parameters.cropRight:]  = background255

        # set any pixel below background threshold to average of all background values
        # TODO: should we just set it to black? or threshold value?
        backPixels    = cv2.compare(self._image, background255, cv2.CMP_LE)
#        backAveClr    = cv2.mean(self._image, mask = backPixels)[0]
        backAveClr    = int(background255)
        backPixelsInv = cv2.bitwise_not(backPixels)

#        plt.imshow(backPixelsInv, 'gray')
#        plt.show()

#        plt.imshow(backPixels, 'gray')#, cmap=plt.cm.binary)
#        plt.show()

        imgKeep     = cv2.bitwise_and(self._image, self._image, mask = backPixelsInv)
        self._image = cv2.add(imgKeep, backAveClr, dst = self._image, mask = backPixels)
#        imgClrArray = np.zeros(self._image.shape[:2], np.uint8)
#        imgClrArray[:] = backAveClr[0]
#        imgClr      = cv2.bitwise_and(imgClrArray, imgClrArray, mask = backPixels)

#        plt.imshow(imgKeep, 'gray')
#        plt.show()

#        plt.imshow(imgClr, 'gray')
#        plt.show()

#        self._image = cv2.add(imgKeep, imgClr, dst = self._image)

#        plt.imshow(self._image, 'gray')
#        plt.show()


    def _CreateAdjustImage(self, genDebugFigure = False):
#        adjustedIm = imadjust(self._image, 0.05, 0.09)
#        self._erodedImg   = im2bw(adjustedIm, 0.5)

        adjustedIm = imadjustCV(self._image, 0.005, 0.05)
        #adjustedIm = imadjustCV(self._image, 0.01, 0.09)
#        self._erodedImg = im2bwCV(adjustedIm, 0.5)
        thresh = 127
        adjustedIm = adjustedIm.astype(np.uint8)
        self._erodedImg = cv2.threshold(adjustedIm, thresh, 255, cv2.THRESH_BINARY)[1]



    def _CreateSobelImage(self, genDebugFigure = False):
        """ Applies a Sobel edge detection to find out where edges are, then dilates and erodes the image.
            In the end, _erodedImg is set to contain filled in regions that are flakes
        """
        sobelH   = cv2.Sobel(self._image, cv2.CV_32F, 1, 0, ksize = 3, scale = 1.0 / 8.0 / 255.)
        sobelV   = cv2.Sobel(self._image, cv2.CV_32F, 0, 1, ksize = 3, scale = 1.0 / 8.0 / 255.)
        sobelMag = cv2.magnitude(sobelH, sobelV)
        
        # TODO: add shortcut to skip images that have no flakes detected...
        
        # threshold by 0.008 (no pixels below 0.008 should remain)
        threshV, threshMag = cv2.threshold(sobelMag, 0.008, 255, cv2.THRESH_BINARY)
        threshMag = np.array(threshMag, dtype = np.uint8)
        dilated   = cv2.dilate(threshMag, self._dilateFilters[self._camId], iterations = 1)
        
        if genDebugFigure:
            self._HelperDrawOrSaveImage(sobelMag,  'Sobel magnitude',           None,  'DEBUG_Sobel_1_sobelMagnitude')
            self._HelperDrawOrSaveImage(threshMag, 'threshold from magnitude',  None,  'DEBUG_Sobel_2_sobelThreshold')
            self._HelperDrawOrSaveImage(dilated,   'dilated',                  'gray', 'DEBUG_Sobel_3_dilated')
            
            # test order of operations between dilation and erosion
            deOrg  = np.array(self._image, dtype = np.uint8)
            deD    = cv2.dilate(deOrg, self._dilateFilters[self._camId], iterations = 1)
            deD    = cv2.erode(deD, self._erodeFilters[self._camId], iterations = 1)
            deDiff = np.absolute(deD - deOrg)
            self._HelperDrawOrSaveImage(deDiff, 'eroded then dilated', 'gray', 'DEBUG_test_erodeThenDilate')
            
            edE    = cv2.erode(deOrg, self._erodeFilters[self._camId], iterations = 1)
            edE    = cv2.dilate(edE, self._dilateFilters[self._camId], iterations = 1)
            edDiff = np.absolute(edE - deOrg)
            self._HelperDrawOrSaveImage(edDiff, 'dilated then eroded', 'gray', 'DEBUG_test_dilateThenErode')
        
        if ImageAnalyzer.openCVVer == 3:
            (_, contours, _) = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        else:
            (contours, _) = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        newImg = np.zeros(self._image.shape, np.uint8)
        for cnt in contours:
            cv2.drawContours(newImg, [cnt], 0, 255, -1)
        
        if genDebugFigure:
            self._HelperDrawOrSaveImage(newImg, 'after contours, before erode', None, 'DEBUG_Sobel_4_contoursBeforeErode')
    
        # Erode the image, perhaps multiple times
        self._erodedImg = cv2.erode(newImg, self._erodeFilters[self._camId], iterations = self._numErosion)
        
        if genDebugFigure:
            # compute and fill out contours once again
            if ImageAnalyzer.openCVVer == 3:
                (_, contours, _) = cv2.findContours(self._erodedImg, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
            else:
                (contours, _) = cv2.findContours(self._erodedImg, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
            w, h   = self._image.shape
            newImg = np.zeros((w, h, 3), np.uint8)
            colors = [(random.random(), random.random(), random.random()) for i in range(10)]
            for i in range(len(contours)):
                # thickness -1 = filled, # = thickness
                color01 = colors[i % len(colors)]
                color   = [255. * v for v in color01]
                cv2.drawContours(newImg, contours, i, color, -1)
            self._HelperDrawOrSaveImage(newImg, 'contours after erode', None, 'DEBUG_Sobel_5_contoursAfterErode')

#        if False:
#            tmp = [
#                ("original image", self._image),
#                ("sobel", sobelMag),
#                ("threshold", threshMag),
#                ("dilated", dilated),
#                ("contours", newImg),
#                ("eroded", self._erodedImg)
#            ]
#
#            fig = plt.figure()
#            cId = 1
#            for d in tmp:
#                a = fig.add_subplot(2, 3, cId)
#                a.set_title(d[0])
#                plt.imshow(d[1])
#                cId += 1
#            fig.show()
#            print "woot"


    def _CreateOtsuImage(self, genDebugFigure = False):
        """ Applies Otsu's Thresholding method after Gaussian Filtering to figure out edges for particles.
            In the end, _erodedImg is set to contain filled in regions that are flakes
        """
        imgBlurred        = cv2.GaussianBlur(self._image, (3, 3), 0)
        thresh, imgThresh = cv2.threshold(imgBlurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if genDebugFigure:
            self._HelperDrawOrSaveImage(imgBlurred, 'blurred input',          None, 'DEBUG_Otsu_1_blurredInput')
            self._HelperDrawOrSaveImage(imgThresh,  'threshold from blurred', None, 'DEBUG_Otsu_2_blurredThreshold')

        # set the low and high thresholds for Canny Edge detection
        threshHi = thresh * 2
        threshLo = thresh * 0.5

        # Canny Edge detection
        # Uses a large Gaussian filter for smoothing and ensuring there are minimal separated edges
        edges           = cv2.Canny(imgBlurred, threshLo, threshHi)
#        self._erodedImg = cv2.GaussianBlur(edges, (7, 7), 0)

        if genDebugFigure:
            self._HelperDrawOrSaveImage(edges, 'edges', None, 'DEBUG_Otsu_3_cannyEdges')

        threshMag = np.array(edges, dtype = np.uint8)
        dilated   = cv2.dilate(threshMag, self._dilateFilters[self._camId], iterations = 1)
#        dilated = cv2.GaussianBlur(edges, (7, 7), 0)

        if genDebugFigure:
            self._HelperDrawOrSaveImage(dilated, 'dilated', None, 'DEBUG_Otsu_4_dilated')

        if ImageAnalyzer.openCVVer == 3:
            (_, contours, _) = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        else:
            (contours, _) = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        newImg = np.zeros(self._image.shape, np.uint8)
        for cnt in contours:
            cv2.drawContours(newImg, [cnt], 0, 255, -1)

        if genDebugFigure:
            self._HelperDrawOrSaveImage(newImg, 'after contours, before erode', None, 'DEBUG_Otsu_5_contoursBeforeErode')

        self._erodedImg = cv2.erode(newImg, self._erodeFilters[self._camId], iterations = self._numErosion)


    def _AnalyzeContour(self, contour, contourMask, nonBackMask, imgIntensityRange, borderPixels):
        """ Analyses a single contour within the image. This contour represents an individual flake within
            the image, in case we have multiple

            :param contour: specific contour of the image. Gotten from cv2.findContours()
            :param contourMask: filled mask of the contour. Gotten from cv2.drawContours()
            :param nonBackMask: pre-computed non-background mask of the entire image
            :param imgIntensityRange: pre-computed image intensity range. Similar to MATLAB's rangefilt()
            :param borderPixels: pre-computed binary image of 1pi border around the image
            :return: dictionary of computed data
        """
        # fitEllipse fails when contour has <5 points
        if len(contour) < 5:
            return None


        # OpenCV image coordinates have (0,0) in top left corner of the image

        # Figure out offsets due to image cropping at capture to offset things
        leftOffset = self._parameters.perCameraCropAtCapture[self._camId][EnumParameterType.CROP_LEFT]
        topOffset  = self._parameters.perCameraCropAtCapture[self._camId][EnumParameterType.CROP_TOP]

        # Take into account offsets for additional crop if selected
        if globalCropImgFlag:
            leftOffset += self._parameters.cropLeft
            topOffset  += self._parameters.cropTop

        # get bounding box (x, y, w, h) as (x, y) is top left corner of the box
        aabb     = list(cv2.boundingRect(contour))
        aabb[0] += leftOffset
        aabb[1] += topOffset

        # area (number of pixels within the contour)
        #contourArea = cv2.contourArea(contour)
        contourArea = cv2.countNonZero(contourMask)

        # perimeter
        contourPerimeter = cv2.arcLength(contour, True)

        # fit ellipse ((x, y), (major, minor), angle)
        ellipse        = list(cv2.fitEllipse(contour))
        ellipse[0]     = list(ellipse[0])
        ellipse[0][0] += leftOffset
        ellipse[0][1] += topOffset

        # mask of non-background pixels within our contour
        contourNonBackMask = cv2.bitwise_and(contourMask, nonBackMask)

        # number of pixels brighter than background within our mask
        flakeArea = cv2.countNonZero(contourNonBackMask)

        # average intensity of the flake
        flakeIntensity = cv2.mean(self._image, mask = contourNonBackMask)
        flakeIntensity = flakeIntensity[0] / 255.

        # maximum intensity of the flake
        m, maxIntensity, ml, Ml = cv2.minMaxLoc(self._image, mask = contourNonBackMask)
        maxIntensity = maxIntensity / 255.

        # get the range of this flake's intensity
        rangeIntensity = cv2.mean(imgIntensityRange, mask = contourNonBackMask)
        rangeIntensity = rangeIntensity[0] / 255.

        # fraction of enclosed area that is brighter than the background
        partialArea = cv2.countNonZero(contourNonBackMask) / float(contourArea)

        # estimate for a degree of focus, on the basis that in focus flakes are both bright and variable
        focus     = flakeIntensity * rangeIntensity
        areaFocus = flakeArea * focus

        # length of flake that touches edge of image frame

        # check if the flake sides touch the edge of cropping box
        if  aabb[0]- 1 <= self._parameters.cropLeft or aabb[0] + aabb[2] + 1 >= (2448 - self._parameters.cropRight): 
            contourMask[ 0,  :] = 255
            contourMask[-1,  :] = 255
            contourMask[ :,  0] = 255
            contourMask[ :, -1] = 255

        borderContour = cv2.bitwise_and(contourMask, contourMask, mask = borderPixels)
        edgeTouch     = cv2.countNonZero(borderContour)

        # for i in [contourMask, borderPixels, borderContour]:
           # plt.imshow(i, 'gray')
           # plt.savefig('something.png')
           # plt.show()


        # Need to return
        return {
            self._ImageFeatureTypeEnum.IFT_BOUNDING_BOX                 : aabb,
            self._ImageFeatureTypeEnum.IFT_FLAKE_CONTOUR_AREA           : contourArea,
            self._ImageFeatureTypeEnum.IFT_FLAKE_CONTOUR_PERIMETER      : contourPerimeter,
            self._ImageFeatureTypeEnum.IFT_ELLIPSE                      : ellipse,
            self._ImageFeatureTypeEnum.IFT_FLAKE_NON_BACKGROUND_AREA    : flakeArea,
            self._ImageFeatureTypeEnum.IFT_FLAKE_PARTIAL_AREA           : partialArea,
            self._ImageFeatureTypeEnum.IFT_AVERAGE_INTENSITY_RANGE      : rangeIntensity,
            self._ImageFeatureTypeEnum.IFT_AVERAGE_INTENSITY            : flakeIntensity,
            self._ImageFeatureTypeEnum.IFT_MAX_INTENSITY                : maxIntensity,
            self._ImageFeatureTypeEnum.IFT_FOCUS                        : focus,
            self._ImageFeatureTypeEnum.IFT_AREA_FOCUS                   : areaFocus,
            self._ImageFeatureTypeEnum.IFT_BOT_LOC_FROM_TOP             : None,         # just in case
            self._ImageFeatureTypeEnum.IFT_EDGE_TOUCH                   : edgeTouch,
        }
