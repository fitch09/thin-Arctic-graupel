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

class ErrorParameterValue(Exception):
    """ Exception thrown when a given parameter is outside of an expected range

        Attributes:
            message - text message showing the error
            value   - parameter value when error occurred
    """
    def __init__(self, message, value):
        self._message = message
        self._value   = value
    def __str__(self):
        return 'ERROR (parameter value): {0} for value \'{1}\''.format(self._message, repr(self._value))


class ErrorOpenConfig(Exception):
    """ Exception thrown when a configuration file can not be opened or found

        Attributes:
            message  - text message showing the error
            filename - full path to the file we tried to open
    """
    def __init__(self, message, filename):
        self._message  = message
        self._filename = filename
    def __str__(self):
        return 'ERROR (open configuration file): {0} for file \'{1}\''.format(self._message, self._filename)


class ErrorConfigKey(Exception):
    """ Exception thrown when a configuration file has a problem with a specific key required to store data

        Attributes:
            message - text message showing the error
            key     - key that is missing
    """
    def __init__(self, message, key):
        self._message = message
        self._key     = key
    def __str__(self):
        return 'ERROR (configuration key): key or parameter \'{1}\', {0}'.format(self._message, self._key)


class ErrorInputSource(ErrorOpenConfig):
    """ Exception thrown when input source can not be opened or found.

        Attributes:
            message  - text message showing the error
            filename - full path to the file we tried to open
    """
    def __str__(self):
        return 'ERROR (input source): {0} for file or path \'{1}\''.format(self._message, self._filename)


