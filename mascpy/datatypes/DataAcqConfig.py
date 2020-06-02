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

import os
from datetime import datetime
import xml.etree.ElementTree as ET
import Timestamp
from Enums import EnumParameterType, EnumTimeParts
from Errors import ErrorOpenConfig

class DataAcqConfig(object):
    """ Stores configuration parameters used for data acquisition by the MASC. This data is typically exported
        every hour (with the first particle) and at the beginning of acquisition. It is assumed that the files are
        time stamped. All data (namely particles) following the time stamps uses the configuration options with a
        prior time stamp.

        For now, stores only the data relevant to image processing
    """
    def __init__(self):
        # when this configuration was generated
        self.timestamp = Timestamp.Timestamp()

        # per camera data
        self.perCamera = None


    def LoadFromXML(self, xmlFileName, nameSchemaParser = None):
        """ Loads all relevant parameters from an XML file based on its name. We can try to decode the filename
            if name schema parser was passed in (of type fileio.FileNameSchema) based on filename's basename.
            If not, we'll use creation date as a timestamp

            :param xmlFileName:      string for xml filename
            :param nameSchemaParser: filename schema decoder
            :return: success flag
        """
        if not os.path.exists(xmlFileName):
            raise ErrorOpenConfig('xml configuration file does not exist', xmlFileName)
        if not os.path.isfile(xmlFileName):
            raise ErrorOpenConfig('xml configuration file is not a file', xmlFileName)

        # figure out timestamp when configuration was saved
        # For now, no timestamp is guaranteed to be saved within the filename. Check if this is the case.
        # If not, look up file creation date
        if nameSchemaParser is not None:
            fileBaseName = os.path.basename(xmlFileName)
            fileTime     = nameSchemaParser.Decode(fileBaseName)
            if fileTime is None:
                return False
            dateStr = '{0:02d}.{1:02d}.{2:4d}'.format(fileTime[EnumTimeParts.MONTH],
                                                      fileTime[EnumTimeParts.DAY],
                                                      fileTime[EnumTimeParts.YEAR])
            timeStr = '{0:02d}:{1:02d}:{2:02d}.000000'.format(fileTime[EnumTimeParts.HOUR],
                                                              fileTime[EnumTimeParts.MINUTE],
                                                              fileTime[EnumTimeParts.SECOND])
            self.timestamp.FromStrings(dateStr, timeStr)
        else:
            creationTime = os.path.getctime(xmlFileName)
            self.timestamp.FromDateTime(datetime.fromtimestamp(creationTime))

        self.perCamera = []

        # parse the file
        config     = ET.parse(xmlFileName)
        configRoot = config.getroot()
        for cElem in configRoot.iter('camera'):
            # TODO: for now, assume that camera ids are in order
            # set some defaults
            fovVal = None
            cropL  = 0
            cropR  = 0
            cropB  = 0
            cropT  = 0

            # FOV element: <fieldOfViewInmm val="0.0306372549"/>
            fovElem = cElem.find('fieldOfViewInmm')
            if fovElem is not None:
                fovVal = float(fovElem.get('val')) * 1000.

            # Cropping info, within <format7Info>, like: <top val="0"/>
            startUpInfo = cElem.find('startUpInfo')
            if startUpInfo is not None:
                format7Info = startUpInfo.find('format7Info')
                if format7Info is not None:
                    topE = format7Info.find('top')
                    if topE is not None:
                        cropT = int(topE.get('val'))

                    botE = format7Info.find('bottom')
                    if botE is not None:
                        cropB = int(botE.get('val'))

                    leftE = format7Info.find('left')
                    if leftE is not None:
                        cropL = int(leftE.get('val'))

                    rightE = format7Info.find('right')
                    if rightE is not None:
                        cropR = int(rightE.get('val'))

            # store camera data
            perCamDict = {
                EnumParameterType.CROP_TOP:             cropT,
                EnumParameterType.CROP_BOTTOM:          cropB,
                EnumParameterType.CROP_LEFT:            cropL,
                EnumParameterType.CROP_RIGHT:           cropR,
                EnumParameterType.CAM_HORIZ_FOV_IN_UM:  fovVal,
            }
            self.perCamera.append(perCamDict)
        return True


    @staticmethod
    def GetListOfConfigs(configFiles, nameSchemaParser = None):
        """ Converts a list of filenames for acquisition configurations into a list of relevant configuration
            options sorted by date (ascending). Timestamps for each file is extracted from the name if schema parser
            is specified, otherwise file creation date is used

            :param configFiles: list of filenames
            :param nameSchemaParser: filename schema parser. If None, file creation time is used
            :return: list of configuration objects
        """
        if configFiles is None or   \
           len(configFiles) is 0 or \
           not isinstance(configFiles[0], DataAcqConfig):
            return None

        # convert all config files into DataAcqConfig objects
        allConfigs = []
        for cf in configFiles:
            co = DataAcqConfig()
            if co.LoadFromXML(cf, nameSchemaParser):
                allConfigs.append(co)
        if len(allConfigs) is 0:
            return None

        # sort objects by date
        allConfigs.sort(key = lambda x: x.timestamp.dateTime)

        return allConfigs


    @staticmethod
    def FindIndexBasedOnTimestamp(configList, timestamp):
        """ Looks through the configList array (list of DataAcqConfig objects) and compares their timestamps to the one
            given. Returns the index of the last object whose time is < given timestamp. If no object like that
            are passed in, returns None. Assumes that data is sorted by timestamp in ascending order.

            :param configList: array of DataAcqConfig objects sorted by timestamp in ascending order
            :param timestamp: timestamp to compare against (datetime type)
            :return: index or None
        """
        if configList is None or   \
           len(configList) is 0 or \
           not isinstance(configList[0], DataAcqConfig):
            return None

        index = -1
        for cfg in configList:
            if cfg.timestamp.dateTime >= timestamp:
                break
            index += 1
        if index is -1:
            return None
        return index
