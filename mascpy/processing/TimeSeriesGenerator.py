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

import math
import datetime
import re
try:
    from datatypes.FlakeInfo import FlakeInfo
    from datatypes.TimeBinInfo import TimeBinInfo
    from datatypes.Enums import EnumTimeParts
    from datatypes.Errors import ErrorParameterValue, ErrorConfigKey
    from datatypes.DataAnalysisConfig import DataAnalysisConfig
except ImportError:
    from FlakeInfo import FlakeInfo
    from TimeBinInfo import TimeBinInfo
    from Enums import EnumTimeParts
    from Errors import ErrorParameterValue, ErrorConfigKey
    from DataAnalysisConfig import DataAnalysisConfig


class TimeSeriesGenerator(object):
    """ Analyzes a list of particles and aggregates their data together based on time bins.
    """

    class Parameters(object):
        """ Parameters used for binning in time
        """

        def __init__(self):
            """ Initialize some default values
            """
            # width of each bin in time (in seconds)
            self.binWidthInSec = 300

            # number of bins that fits in an hour
#            self._numBinsPerHour = int(math.ceil(3600. / self.binWidthInSec))

            # maximum particle fallspeed required for the particle to be averaged into a bin (m/s)
            self.maxFallSpeed = 5

            # minimum number of particles used for average required for stats to be "good"
            self.minNumParticles = 10


        def _CheckParameters(self):
            """ Checks whether parameters are acceptable. If not, prints appropriate error message
            """
            # check bin width in seconds
            if self.binWidthInSec is None:
                raise ErrorParameterValue('time binning width parameter set to None', None)
            else:
                if self.binWidthInSec < 1 or \
                   self.binWidthInSec > 3600:
                    raise ErrorParameterValue('time binning width parameter outside range [1, 3600] sec', self.binWidthInSec)
                if not 3600 % self.binWidthInSec == 0:
                    raise ErrorParameterValue('time binning width parameter must divide hour (3600 sec) exactly', self.binWidthInSec)

            # check fallspeed
            if self.maxFallSpeed is None:
                raise ErrorParameterValue('time binning max fallspeed parameter set to None', None)
            else:
                if self.maxFallSpeed <= 0 or \
                   self.maxFallSpeed > 1000:
                    raise ErrorParameterValue('time binning max fallspeed parameter outside range (0, 1000] m/s', self.maxFallSpeed)

            # check minimum number of particles per bin
            if self.minNumParticles is None:
                raise ErrorParameterValue('time binning minimum number of particles per bin parameter is None', None)
            else:
                if self.minNumParticles <= 0:
                    raise ErrorParameterValue('time binning minimum number of particles per bin parameter must be >0', self.minNumParticles)


        def InitFromTimeDescription(self, descriptionStr):
            """ Initializes time binning width based on the input string describing the time. Will perform parameter
                check afterwards. The string can be specified using # and one of these characters h, m, s
                corresponding to hours, minutes, and seconds respectively. Some examples: 10s, 5m, 1h, 2m24s

                :param descriptionStr: string describing time bin width
            """
            pieces       = re.split('[hms]', descriptionStr)
            accumTimeInS = 0
            for p in pieces:
                pLen = len(p)
                if pLen > 0:
                    pId  = descriptionStr.find(p)
                    tVal = float(p)

                    # figure out what was following this number (h,m or s)
                    # add accumulate seconds appropriately. If seconds, we must round down
                    tStr = descriptionStr[pId + pLen].lower()
                    if tStr == 'h':
                        accumTimeInS += tVal * 60 * 60
                    elif tStr == 'm':
                        accumTimeInS += tVal * 60
                    elif tStr == 's':
                        accumTimeInS += math.floor(tVal)
                    else:
                        raise ErrorParameterValue('time binning width parameter can\'t have strings other than h,m,s', descriptionStr)
            self.binWidthInSec = int(math.floor(accumTimeInS))

            self._CheckParameters()


        def InitFromJSONDict(self, rootSettings):
            """ Initializes all parameters based on input dictionary, which is assumed to be generated from
                importing JSON representation (either string or a file)

                :param rootSettings: JSON dict with data
            """
             # check that we have correct dictionary
            try:
                allSettings = rootSettings['timeBinningParameters']
            except KeyError as e:
                raise ErrorConfigKey('time binning parameters json has wrong root key, not \'timeBinningParameters\'', None)

            # double check that all keys we have within root are the same as we expect
            allRootKeys = [
                'binWidthInSec',
                'maxFallSpeedInMetersPS',
                'minNumParticlesPerBin',
            ]
            DataAnalysisConfig.KeyChecker(allSettings, allRootKeys, 'timeBinningParameters', 'time binning parameters json')

            # now update values using whatever was passed in
            if 'binWidthInSec'          in allSettings:
                self.binWidthInSec      =  allSettings['binWidthInSec']
            if 'maxFallSpeedInMetersPS' in allSettings:
                self.maxFallSpeed       =  allSettings['maxFallSpeedInMetersPS']
            if 'minNumParticlesPerBin'  in allSettings:
                self.minNumParticles    =  allSettings['minNumParticlesPerBin']

            self._CheckParameters()


        def GetJSONDict(self):
            """ Gets the dictionary which encodes the parameters using JSON data. The dictionary returned encodes
                both the data and the key string used within JSON using 'data' and 'key' keys within.

                :return: dictionary
            """
            jsonKey  = 'timeBinningParameters'
            jsonData = {
                'binWidthInSec':          int  (self.binWidthInSec),
                'maxFallSpeedInMetersPS': float(self.maxFallSpeed),
                'minNumParticlesPerBin':  int  (self.minNumParticles),
            }
            return {
                'key':  jsonKey,
                'data': jsonData
            }


    def __init__(self, parameters = None):
        """ Initializes things so that each hour would be split into bins of specified widths

            :param parameters: binning parameters to be used in analysis
        """
        if parameters is None:
            self._parameters = self.Parameters()
        else:
            self._parameters = parameters


    def AnalyzeParticles(self, data):
        """ Runs through the list of particles and averages them into bins. Particles that fall into a bin
            are collected before being averaged. During the process, each particle is filtered based on
            binning parameters.

            The number of bins used for output is determined by the range of particle dates that weer passed in.
            The boundaries are rounded to the hour, floor for first and ceil for last.

            :param data: list of particles (FlakeInfo objects) to be averaged.
            :return: list of bins
        """
        # check input
        if data is None   or \
           len(data) == 0 or \
           not isinstance(data[0], FlakeInfo):
            return None

        def GetDateHourBin(particle, fromHourL, binWidthInSec):
            """ Helper to convert current particle's time into a bin offset where that particle belongs. Returns
                a dictionary outlining particle parameters used in placing it into the bin

                :param particle: particle object FlakeInfo.FlakeInfo
                :param fromHourL: datetime object with the first hour that's from boundary for bins
                :param binWidthInSec: how wide a bin is in seconds
                :return: dictionary
            """
            partData = particle.captureDateTime
            if partData is None or \
               partData.dateStr is '':
                return None

            hourDiffL   = partData.dateTime - fromHourL
            numSecondsL = hourDiffL.days * (24 * 60 * 60) + hourDiffL.seconds + hourDiffL.microseconds / 1000000.
            thisBin     = int(math.floor(numSecondsL / binWidthInSec))

            dateComp   = partData.GetComponents()
            return {
                'date':   partData.dateStr,
                'hour':   dateComp[EnumTimeParts.HOUR],
                'bin':    thisBin,
            }

        # shortcut
        binWidthInSec   = self._parameters.binWidthInSec
        maxFallSpeed    = self._parameters.maxFallSpeed
        minNumParticles = self._parameters.minNumParticles

        # binning has to be aligned at hourly boundary. So first, we must find out the first hour bounding the data
        fromHour = data[0].captureDateTime.dateTime
        fromHour = fromHour.replace(minute = 0, second = 0, microsecond = 0)

        # to hour, with rounding up the hour
        toHour  = data[-1].captureDateTime.dateTime
        toHour  = toHour.replace(minute = 0, second = 0, microsecond = 0)
        toHour += datetime.timedelta(hours = 1)

        # total number of seconds our bins have to represent. Find the number and pre-allocate
        hourDiff   = toHour - fromHour
        numSeconds = hourDiff.days * (24 * 60 * 60) + hourDiff.seconds + hourDiff.microseconds / 1000000.
        numBins    = int(math.ceil(numSeconds / binWidthInSec))

        # pre-generate output bin structures
        binsToRet  = [None] * numBins
        for b in range(0, numBins):
            binCenterInSec = (b + 0.5) * binWidthInSec
            binCenter      = fromHour + datetime.timedelta(seconds = binCenterInSec)
            binObj         = TimeBinInfo(binCenter, binWidthInSec)
            binsToRet[b]   = binObj

        particles = []

        # set up info for current bin
        curDate   = None
        curHour   = None
        curBin    = None

        # run through all given data
        for datum in data:
            # get info about this particle
            partInfo = GetDateHourBin(datum, fromHour, binWidthInSec)
            if partInfo is None:
                continue

            # check if this particle belongs in the current bucket
            if curDate   == partInfo['date']   and \
               curHour   == partInfo['hour']   and \
               curBin    == partInfo['bin']:
                particles.append(datum)

            # current bin is filled, so process it
            else:
                if curBin is not None:
                    binsToRet[curBin].Average(particles, maxFallSpeed, minNumParticles)
                    particles = []

                # set current values (will be an update only when they don't match)
                curDate   = partInfo['date']
                curHour   = partInfo['hour']
                curBin    = partInfo['bin']
                particles.append(datum)

        # process the final bin
        if curBin is not None:
            binsToRet[curBin].Average(particles, maxFallSpeed, minNumParticles)

        return binsToRet
