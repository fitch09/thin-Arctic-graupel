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

from ImageInfo import ImageInfo
from ImageAnalysisInfo import ImageAnalysisInfo
from Enums import EnumParserColumns
from Timestamp import Timestamp
from DataToStringConverter import DataToStringConverter


class FlakeInfo(object):
    """ Describes a hydrometeor that was captured by the MASC including fallspeed and all
        related images. This includes data derived from the images as well. Effectively this is a simple
        container for relevant information.

        The following data is recorded per particle:
         - particle id - at least 0, has no limit
         - capture time and date - extracted from data info file
         - fallspeed
         - collection of images taken by the instrument (and within each its analysis information)
         - aggregated analysis derived from individual camera images
    """

    # string names and data format for each column we will write out
    dataStringifier = DataToStringConverter([
        ['particle id',                             '{0}'],
        ['particle capture date (mm.dd.yyyy)',      '{0}'],
        ['particle capture time (hh:mm:ss.mmmmmm)', '{0}'],
        ['fallspeed (m/s)',                         '{0}'],
    ])

    def __init__(self):
        """ Basic initialization of all data, which defaults to None for all fields
        """
        # data constant per hydrometeor
        # fall speed (in m/s)
        self.fallSpeedInMPS = None

        # date and time when this particle was captured
        self.captureDateTime = None

        # flake id
        self.flakeId = None

        # dict with images we captured, key is camera id (int), value is ImageInfo
        self.imageData = []

        # aggregated information from all of the images
        self.aggregatedAnalysisResults = ImageAnalysisInfo()


    def SetFallspeed(self, fallspeedData):
        """ Sets the fields relevant to data stored in Fallspeed data output file. The particle
            is not reset, therefore all previous other data stored here will remain.

            :param fallspeedData: dictionary with data information output by fileio.DataFileParser.FallspeedDataParser
        """

        if EnumParserColumns.FLAKE_ID in fallspeedData:
            self.flakeId = fallspeedData[EnumParserColumns.FLAKE_ID]

        if EnumParserColumns.DATE_STR in fallspeedData and \
           EnumParserColumns.TIME_STR in fallspeedData:
            self.captureDateTime = Timestamp()
            self.captureDateTime.FromStrings(fallspeedData[EnumParserColumns.DATE_STR], \
                                             fallspeedData[EnumParserColumns.TIME_STR])

        if EnumParserColumns.FALL_SPEED in fallspeedData:
            self.fallSpeedInMPS = fallspeedData[EnumParserColumns.FALL_SPEED]


    def AddImage(self, imageData):
        """ Adds an image data into the list. The particle is not reset, therefore all previous
            othe data store here will remain.

            :param imageData: dictionary with image data information output by fileio.DataFileParser.ImageDataParser
        """
        newImg = ImageInfo()
        newImg.SetData(imageData)
        self.imageData.append(newImg)


    def GetString(self, delimiter):
        """ Generates a string with the data meant for output. Each element is separated by a delimiter.
            The data is written out in the following format (each column):
              1. particle id
              2. particle capture date
              3. particle capture time
              4. fallspeed

            :param delimeter: string delimiter separating each column
            :return: string
        """
        # this is a bit slower, but should be easier to add items to
        # NOTE: the order here has to be the same as in the self.dataStringifier
        dataToPrint = [
            self.flakeId,
            self.captureDateTime.dateStr,
            self.captureDateTime.timeStr,
            self.fallSpeedInMPS,
        ]
        return self.dataStringifier.GetString(dataToPrint, delimiter)


    def Print(self, stringPrepend = ""):
        """ Basic print functionality

            :param stringPrepend: prepended before each print statement. Intended for spaces
        """   
        subSpaceStr = stringPrepend + '    '
        print "{0}particle id: {1}".format(stringPrepend, self.flakeId)
        if self.captureDateTime is not None:
            self.captureDateTime.Print(stringPrepend + ' ')
        else:
            Timestamp.PrintAsNone(stringPrepend + ' ')
        print "{0}  - fallspeed \"{1}\" (m/s)".format(stringPrepend, self.fallSpeedInMPS)
        print "{0}  - images ({1}):".format(stringPrepend, len(self.imageData))
        for img in self.imageData:
            img.Print(subSpaceStr)
            print "{0}-----".format(subSpaceStr)
        print "{0}  - aggregated analysis:".format(stringPrepend, self.aggregatedAnalysisResults)
        self.aggregatedAnalysisResults.Print(subSpaceStr)


    def IsGoodForAveraging(self, maxVelThreshold):
        """ Checks whether this particle can be averaged by checking its fallspeed against a max threshold
            and whether analysis results are also appropriate for averaging

            :param maxVelThreshold: maximum velocity in m/s
            :return: flag if this particle can be averaged with others
        """
        return self.fallSpeedInMPS is not None    and \
           self.fallSpeedInMPS <= maxVelThreshold and \
           self.aggregatedAnalysisResults.IsGoodForAveraging(True)
