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
from ImageAnalysisInfo import ImageAnalysisInfo
from FlakeInfo import FlakeInfo
from Timestamp import Timestamp


class TimeBinInfo(object):
    """ Container for analysis data gathered from aggregating particles within a time bin together
    """
    class QualityCheck(object):
        """ Helper to define the types of quality checks we can pass after analyzing each particle.
        """
        def __init__(self):
            """ Initializes all quality parameters to False
            """
            self.passedAllChecks        = False
            self.passedMinNumParticles  = False

    # string names and data format for each column to write out
    dataStringifier = DataToStringConverter([
        ['bin center date (mm.dd.yyyy)',      '{0}'],
        ['bin center time (hh:mm:ss.mmmmmm)', '{0}'],
        ['bin width (sec)',                   '{0}'],
        ['total num particles',               '{0}'],
        ['num particles used for avg',        '{0}'],
        ['passed quality check (0, 1)',       '{0:d}'],
        ['average fall speed (m/s)',          '{0}'],
    ])


    def __init__(self, binCenter, binWidthInSec):
        """ Initializes the bin and sets up rudimentary info about it. We assume that an hour is divisible by bin
            widths, and a bin width is at most an hour (this is assumed). The bin is a simple container for
            analyzed data.

            :param binCenter: timestamp corresponding to center of the bin as datetime object
            :param binWidthInSec: width of the bin in seconds
        """
        # center of this bin in time
        self.binCenter = Timestamp()
        self.binCenter.FromDateTime(binCenter)

        # width of this bin in time (in seconds)
        self.binWidthInSec = binWidthInSec

        # analysis average
        self.aveFallSpeed    = None
        self.analysisAverage = ImageAnalysisInfo()

        # total number of all particles that we got within this bin. This includes particles that were not "good"
        self.totalNumParticles = 0

        # total number of particles that contributed to the average. Note only "good" particles can
        # For example, particle's flatness parameter must be not None
        self.numUsedForAve = 0

        # quality variables
        self.quality = TimeBinInfo.QualityCheck()


    def Average(self, infos, maxFallSpeed, minNumParticles):
        """ Sets our values to the averages of data that was passed in. The data is assumed to be an array
            of FlakeInfo() objects. We will rely on their aggregatedAnalysisResults that was calculated averaging
            images (so ImageAnalysisInfo.isBuiltFromAverage == True). If flatness parameter is None, then particle is
            not accepted

            :param infos: array of FlakeInfo() objects to average
            :param maxFallSpeed: fallspeed max filter to consider particle for averaging
            :param minNumParticles: minimum number of flakes averaged in bin to consider it statistically significant
        """
        self.totalNumParticles = 0
        self.numUsedForAve     = 0

        # just in case
        if infos is None   or \
           len(infos) == 0 or \
           not isinstance(infos[0], FlakeInfo):
            return

        # count how many particles are good
        self.totalNumParticles = len(infos)
        numGoodParticles    = 0
        for i in infos:
            if i.IsGoodForAveraging(maxFallSpeed):
                numGoodParticles += 1
        if numGoodParticles == 0:
            # TODO: count this occurrence?
            return

        # average appropriate data by building a list of good particles
        self.numUsedForAve  = numGoodParticles
        self.aveFallSpeed   = 0
        goodParticles       = []
        for i in infos:
            if i.IsGoodForAveraging(maxFallSpeed):
                self.aveFallSpeed += i.fallSpeedInMPS
                goodParticles.append(i.aggregatedAnalysisResults)
        self.analysisAverage.Average(goodParticles, True)
        self.aveFallSpeed /= numGoodParticles

        # check the numbers of particles actually agree
        # This should always be true
        if not numGoodParticles == len(goodParticles) or \
           not numGoodParticles == self.analysisAverage.numUsedForAverage:
            return

        # perform quality check against what we've computed
        # Even if we fail the quality check, the data will remain in case thresholds are too aggressive
        passNumParticles = self.numUsedForAve >= minNumParticles

        self.quality.passedMinNumParticles = passNumParticles
        self.quality.passedAllChecks       = passNumParticles


    def GetString(self, delimiter):
        """ Generates a string with the data meant for output. Each element is separated by a delimiter.
            The data is written out in the following format (each column):
              1. bin center date
              2. bin center time
              3. bin width (seconds)
              4. passed quality check flag (0, 1)
              5. total number of particles that fell into this bin
              6. num particles used for average
              7. average fallspeed (m/s)

            :param delimiter: string delimiter separating each column
            :return: string
        """
        # this is a bit slower, but should be easier to add items to
        # NOTE: the order here has to be the same as in the self.dataStringifier
        dataToPrint = [
            self.binCenter.dateStr,
            self.binCenter.timeStr,
            self.binWidthInSec,
            self.totalNumParticles,
            self.numUsedForAve,
            self.quality.passedAllChecks,
            self.aveFallSpeed,
        ]
        return self.dataStringifier.GetString(dataToPrint, delimiter)


    def Print(self, stringPrepend = ""):
        """ Basic print functionality

            :param stringPrepend: prepended before each print statement. Intended for spaces
        """
        print '{0}bin center date time: {1} {2}'        .format(stringPrepend, self.binCenter.dateStr, self.binCenter.timeStr)
        print '{0}  - bin width:             {1} (s)'   .format(stringPrepend, self.binWidthInSec)
        print '{0}  - total num particles:   {1}'       .format(stringPrepend, self.totalNumParticles)
        print '{0}  - num particles for avg: {1}'       .format(stringPrepend, self.numUsedForAve)
        print '{0}  - passed quality:        {1:d}'     .format(stringPrepend, self.quality.passedAllChecks)
        print '{0}  - ave fallspeed:         {1} (m/s)' .format(stringPrepend, self.aveFallSpeed)
        self.analysisAverage.Print(stringPrepend + ' ')
