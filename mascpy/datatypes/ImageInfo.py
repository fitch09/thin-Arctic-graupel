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

from ImageAnalysisInfo     import ImageAnalysisInfo
from Timestamp             import Timestamp
from Enums                 import EnumParserColumns
from DataToStringConverter import DataToStringConverter


class ImageInfo(object):
    """ Describes original image input as well as any information derived from analyzing it.
        By default, all data is initialized to None. This class only stores the data.

        The following is recorded:
         - image acquisition time and date
         - image file name to be used during analysis
         - camera id for the image
         - analysis results for the image
    """

    # string names and data format for each column we will write out
    dataStringifier = DataToStringConverter([
        ['camera id', '{0}'],
        ['filename',  '{0}'],
    ])

    def __init__(self):
        """ Sets up the data to defaults, each as None
        """
        # file name corresponding to this image (assumes correct path)
        self.fileName = None

        # date and time when this image was captured
        self.captureDateTime = None

        # camera index which captured this image
        self.cameraId = None

        # Note: the date/time when the hydrometeor was captured will be different from the time stamp
        #       assigned to the image (within ~1 sec), and most definitely different from when the image
        #       was actually written to disk. This time can be reliable only when fallspeed data timestamp
        #       fails.

        self.analysisResults = ImageAnalysisInfo()


    def SetData(self, imageData):
        """ Sets an image data without disturbing previously stored data.

            :param imageData: dictionary with image data information output by fileio.DataFileParser.ImageDataParser
        """
        # Note: we ignore flakeId (redundant info) and frameTimeStamp (is usually 0)
        if EnumParserColumns.CAMERA_ID in imageData:
            self.cameraId = imageData[EnumParserColumns.CAMERA_ID]

        if EnumParserColumns.DATE_STR in imageData and \
           EnumParserColumns.TIME_STR in imageData:
            self.captureDateTime = Timestamp()
            self.captureDateTime.FromStrings(imageData[EnumParserColumns.DATE_STR],
                                             imageData[EnumParserColumns.TIME_STR])

        if EnumParserColumns.IMAGE_NAME_STR in imageData:
            self.fileName = imageData[EnumParserColumns.IMAGE_NAME_STR]


    def GetString(self, delimiter):
        """ Generates a string with the data meant for output. Each element is separated by a delimiter.
            The data is written out in the following format (each column):
              1. camera id
              2. filename

            :param delimeter: string delimiter separating each column
            :return: string
        """
        # this is a bit slower, but should be easier to add items to
        # NOTE: the order here has to be the same as in the self.dataStringifier
        dataToPrint = [
            self.cameraId,
            self.fileName,
        ]
        return self.dataStringifier.GetString(dataToPrint, delimiter)


    def Print(self, stringPrepend = ""):
        """ Simple print function

            :param stringPrepend: string to prepend for each print call (intended for spaces)
        """
        print "{0} - filename:       \"{1}\"".format(stringPrepend, self.fileName)

        self.captureDateTime.Print(stringPrepend)
        self.analysisResults.Print(stringPrepend)
