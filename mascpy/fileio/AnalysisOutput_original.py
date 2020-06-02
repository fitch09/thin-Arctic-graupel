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


from datatypes.FlakeInfo import FlakeInfo
from datatypes.ImageInfo import ImageInfo
from datatypes.ImageAnalysisInfo import ImageAnalysisInfo
from datatypes.TimeBinInfo import TimeBinInfo


class AnalysisOutput(object):
    """ Writes out analyzed data in various formats.
    """

    @staticmethod
    def GetHeaderStringPerImage(delimiter):
        """ Gets the string for the header of the output file where analysis for each image is written out into a
            single file. The columns are aggregated in the following manner:
              1-4 see FlakeInfo.dataStringifier for format
              5-6 see ImageInfo.dataStringifier for format
              7+  see ImageAnalysisInfo.dataStringifier for format

            :param delimiter: string to delimit the separation between columns
            :return: string
        """
        flakeStr = FlakeInfo.dataStringifier.GetHeaderString(delimiter)
        imgStr   = ImageInfo.dataStringifier.GetHeaderString(delimiter)
        anlStr   = ImageAnalysisInfo.dataStringifierRaw.GetHeaderString(delimiter)
        return '{1}{0}{2}{0}{3}\n'.format(delimiter, flakeStr, imgStr, anlStr)


    @staticmethod
    def GetHeaderStringPerParticle(delimiter):
        """ Gets the string for the header of the output file where analysis for each particle is written out into a
            single file. The columns are aggregated in the following manner:
              1-4 see FlakeInfo.dataStringifier for format
              5+  see ImageAnalysisInfo.dataStringifier for format

            :param delimiter: string to delimit the separation between columns
            :return: string
        """
        flakeStr = FlakeInfo.dataStringifier.GetHeaderString(delimiter)
        anlStr   = ImageAnalysisInfo.dataStringifierAve.GetHeaderString(delimiter)
        return '{1}{0}{2}\n'.format(delimiter, flakeStr, anlStr)


    @staticmethod
    def GetHeaderStringPerTimeBin(delimiter):
        """ Gets the string for the header of the output file where averages for all particles falling into
            specific time bins

        :param delimiter:
        :return: string
        """
        binStr = TimeBinInfo.dataStringifier.GetHeaderString(delimiter)
        anlStr = ImageAnalysisInfo.dataStringifierAve.GetHeaderString(delimiter)
        return '{1}{0}{2}\n'.format(delimiter, binStr, anlStr)


    @staticmethod
    def WriteDataPerImage(data, fileObj, dataIndex, delimiter, lock = None):
        """ Writes out the data per image to an ASCII file (provided as an object). Columns are written out in the
            following order:
              1-4 see FlakeInfo.GetString() function for format
              5-6 see ImageInfo.GetString() function for format
              7+  see ImageAnalysisInfo.GetString() function for format

            :param data: dictionary of array of FlakeInfo
            :param fileObj: output object used for output
            :param dataIndex: index for the data subset of which we're processing. Used by fileObj
            :param delimiter: string to delimit the separation between columns
            :param lock: lock to protect parallel writer (needs to be shared by Pool objects)
        """
        # check input
        if fileObj is None or \
           data    is None or \
           len(data) == 0 or  \
           not isinstance(data[0], FlakeInfo):
            return

        # generate a string with all of the data
        strToWrite = ''
        # row = 0
        for datum in data:
            flakeStr = datum.GetString(delimiter)


            # Extra qualification to identify the rain drops based on the pixel intensity and variability
            # and also the number of the particles.
            rain = []
            for inx, img in enumerate(datum.imageData):
                if img.analysisResults.quality.passedAllChecks == 0:
                    rain.append('Nan')
                elif (img.analysisResults.meanPixelIntensity > 0.3 or img.analysisResults.meanPixelIntensityVariability > 0.3 or img.analysisResults.numObjects > 2):
                    rain.append(1)
                else: 
                    rain.append(0)

            # Set rain to 1 for all three images if rain is identifies in at least two of images, or rain is identified in 
            # one but two others have zero for rain, or rain is identified in one but rain for two others are 0 and NA.
            # Set rain to 0 for all three images if all three gets 0 value for rain, or two gets zero and the other one gets NA.
            # Set rain to NA for all three images if at least two of the images get NA value for the rain.
            rain_final = 0
            nan , zero, one = 0, 0, 0
            for i in range(3):
                if rain[i] == 'Nan':
                    nan +=1
                if rain[i] == 0:
                    zero += 1
                if rain[i] == 1:
                    one +=1

            if nan >= 2:
                rain_final = 'Nan'
            elif (zero >= 2) and (one != 1):
                rain_final = 0
            else:
                rain_final = 1

            # Set rain_final for each particle_id instead of for each image.
            for img in datum.imageData:
                img.analysisResults.rain_final = rain_final

            for img in datum.imageData:
                imgStr = img.GetString(delimiter)
                anlStr = img.analysisResults.GetTableString(delimiter)
                strToWrite += '{1}{0}{2}{0}{3}\n'.format(delimiter, flakeStr, imgStr, anlStr)

        # write it all out to the file object
        fileObj.Write(strToWrite, dataIndex, lock)


    @staticmethod
    def WriteDataPerParticle(data, fileObj, dataIndex, delimiter, lock = None):
        """ Writes out the data per particle to an ASCII file (provided as an object). Columns are written out in the
            following order:
              1-4 see FlakeInfo.GetString() function for format
              5+  see ImageAnalysisInfo.GetString() function for format

            :param data:      dictionary of array of FlakeInfo
            :param fileObj:   output object used for output
            :param dataIndex: index for the data subset of which we're processing. Used by fileObj
            :param delimiter: string to delimit the separation between columns
            :param lock:      lock to protect parallel writer (needs to be shared by Pool objects)
        """
        # check input
        if fileObj is None or \
           data    is None or \
           len(data) == 0 or  \
           not isinstance(data[0], FlakeInfo):
            return

        # generate a string with all of the data
        strToWrite = ''
        for datum in data:
            # we should save ONLY the particles that have been averaged
            if not datum.aggregatedAnalysisResults.IsGoodForAveraging():
                continue
            flakeStr = datum.GetString(delimiter)
            anlStr   = datum.aggregatedAnalysisResults.GetTableString(delimiter)
            strToWrite += "{1}{0}{2}\n".format(delimiter, flakeStr, anlStr)

        # write it all out to the file object
        fileObj.Write(strToWrite, dataIndex, lock)


    @staticmethod
    def WriteDataPerTimeBin(data, fileObj, dataIndex, delimiter, lock = None):
        """ Writes out the data per time bin to an ASCII file (provided as an object). Columns are written out in the
            following order:
              1-6 see TimeBinInfo.GetString() function for format
              7+  see ImageAnalysisInfo.GetString() function for format

            :param data:      dictionary of array of TimeBinInfo
            :param fileObj:   output object used for output
            :param dataIndex: index for the data subset of which we're processing. Used by fileObj
            :param delimiter: string to delimit the separation between columns
            :param lock:      lock to protect parallel writer (needs to be shared by Pool objects)
        """
        # check input
        if fileObj is None or \
           data    is None or \
           len(data) == 0 or  \
           not isinstance(data[0], TimeBinInfo):
            return

        # generate a string with all of the data
        strToWrite = ''
        for datum in data:
            binStr = datum.GetString(delimiter)
            anlStr = datum.analysisAverage.GetTableString(delimiter)
            strToWrite += '{1}{0}{2}\n'.format(delimiter, binStr, anlStr)

        # write it all out to the file object
        fileObj.Write(strToWrite, dataIndex, lock)


    @staticmethod
    def FlushWritingToFile(fileObj):
        """ Flushes the file to disk

            :param fileObj: output object used for output
        """
        fileObj.FlushWritingToFile()
