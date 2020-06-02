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
import json
from Errors import ErrorOpenConfig, ErrorConfigKey


class DataAnalysisConfig(object):
    """ Provides parser for analysis parameters stored in JSON format. This configuration file will be used
        for default values before processing images and binning analysis in time.
    """

    @staticmethod
    def LoadFromJSONFile(jsonFile):
        """ Loads a json file and return a dictionary representing the data.

            :param jsonFile: filename to load data from
            :return: dictionary with data or None
        """
        if not os.path.exists(jsonFile):
            raise ErrorOpenConfig('image analysis parameter json file does not exist', jsonFile)
        if not os.path.isfile(jsonFile):
            raise ErrorOpenConfig('image analysis parameter json file is not a file', jsonFile)

        with open(jsonFile, 'r') as jf:
            return json.load(jf)


    @staticmethod
    def LoadFromJSONString(inString):
        """ Loads a json string and returns a dictionary representing the data.

            :param inString: parameters as a JSON-formatted string
            :return: dictionary with data
        """
        return json.loads(inString)


    @staticmethod
    def GetJSONString(arrayOfDicts, indentWidth = None):
        """ Given an array of dictionaries describing JSON values, combines them together and returns a
            single JSON string representation. Each dictionary is assumed to have two keys: 'key' corresponds
            to a string describing the data, and 'data' which is a dictionary representing JSON data to store.

            :param arrayOfDicts: array of dictionaries to combine
            :param indentWidth:  indent to use to offset each line for pretty print. None has no indent
            :return: string representing JSON
        """
        # build up dictionary from pieces we got
        masterDict = {}
        for d in arrayOfDicts:
            key   = d['key']
            value = d['data']
            masterDict[key] = value
        return json.dumps(masterDict, indent = indentWidth)


    @staticmethod
    def KeyChecker(dictToCheck, acceptKeys, rootKey, errString):
        """ Helper to check whether dictionary contains expected keys within. If not throws an error

            :param dictToCheck: dictionary to check
            :param acceptKeys:  list of accepted keys
            :param rootKey:     name of the root element under which acceptKeys live
            :param errString:   error string to prepend, specifying the type of dictionary we're checking
        """
        for key in dictToCheck:
            # automatically skip anything that contains 'comment' in it
            if 'comment' in key:
                continue

            # check if key is in here
            if key not in acceptKeys:
                errMsg = '{0} has unacceptable key under root \'{1}\'. Acceptable keys are \'{2}\''.format(errString,
                                                                                                           rootKey,
                                                                                                           acceptKeys)
                raise ErrorConfigKey(errMsg, key)
