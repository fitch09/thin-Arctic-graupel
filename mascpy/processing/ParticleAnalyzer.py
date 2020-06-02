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

from ImageAnalyzer import ImageAnalyzer
try:
    from datatypes.FlakeInfo import FlakeInfo
except ImportError:
    from FlakeInfo import FlakeInfo


class ParticleAnalyzer(object):
    """ Basically runs through the given particles and analyzes all of the images within. Then computes an average
        of their data
    """

    def __init__(self, parameters):
        """ Basic initialization. Parameters are passed into the per-image analyser

            :param parameters: parameters guiding image analysis. See ImageAnalyzer.Parameters()
        """
        self._imgAnalyzer = ImageAnalyzer(parameters)


    def UpdateFromConfig(self, dataAckParams):
        """ Updates parameters that depend on acquisition parameters.

            :param dataAckParams: Parameters of type DataAcqConfig
        """
        self._imgAnalyzer.UpdateFromConfig(dataAckParams)


    def UpdateFromJSONDict(self, newConfig):
        """ Updates parameters that depend on acquisition parameters, using JSON dictionary

            :param newConfig: JSON dictionary with new values
        """
        self._imgAnalyzer.UpdateFromJSONDict(newConfig)


    def AnalyzeParticles(self, data):
        """ Runs through the particle list, analyzes each image and then aggregates all that data together
            per particle

            :param data: list of FlakeInfo() objects
        """
        # check input
        if data is None   or \
           len(data) == 0 or \
           not isinstance(data[0], FlakeInfo):
            return

        # run through all of the given data, and analyze each image individually
        c = 0
        for datum in data:
            c += 1
#            # TODO: removeme
#            if c > 40:
#                break
            # analyze individual camera images
            allImgs = []
            for img in datum.imageData:
                self._imgAnalyzer.AnalyzeImage(img)
                allImgs.append(img.analysisResults)


            # aggregate these measures together
            datum.aggregatedAnalysisResults.Average(allImgs)


    @staticmethod
    def FindIndexBasedOnTimestamp(data, timestamp):
        """ Looks through the data array (list of FlakeInfo objects) and compares their timestamps to the one
            given. Returns the index of the last object whose time is < given timestamp. If no object like that
            are passed in, returns None. Assumes that data is sorted by timestamp in ascending order.

            :param data: array of FlakeInfo objects sorted by timestamp in ascending order
            :param timestamp: timestamp to compare against (datetime type)
            :return: index or None
        """
        # check input
        if data is None or   \
           len(data) == 0 or \
           not isinstance(data[0], FlakeInfo):
            return None

        # run through all given data, and compare timestamps
        index = -1
        for datum in data:
            if datum.captureDateTime.dateTime >= timestamp:
                break
            index += 1
        if index == -1:
            return None
        return index
