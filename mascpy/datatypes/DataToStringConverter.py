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

class DataToStringConverter(object):
    """ Helper to create strings for headers and actual data based on the input names and formats.
    """

    def __init__(self, columnHeaders):
        """ Basic initialization. The headers are supplied in the format: list of arrays sized 2 =
            [string for header, string for format to print data]

            :param columnHeaders:
        """
        self._columnHeaders = columnHeaders


    def GetString(self, dataToPrint, delimiter):
        """  Generates a string with the data meant for output. Each element is separated by a delimiter.

            :param delimiter: string delimiter separating each column
            :return: string
        """
        if not len(dataToPrint) == len(self._columnHeaders):
            return ''
        asStrings = []
        for data, format in zip(dataToPrint, self._columnHeaders):
            if data is None:
                asStrings.append('Nan')
            else:
                fstr = '{0}'.format(format[1])
                asStrings.append(fstr.format(data))
        return delimiter.join(asStrings)


    def GetHeaderString(self, delimiter):
        """ Gets the string to identify the headers for each column. If the delimiter is a space, then
            all spaces within each column header is replaced by an _.

            :param delimiter: string delimiter separating each column
            :return: string
        """
        if not delimiter == ' ':
            return delimiter.join([x[0] for x in self._columnHeaders])
        else:
            str = ''
            for i in range(1, len(self._columnHeaders) - 1):
                str += "{0}{1}".format(self._columnHeaders[i][0], delimiter)
            str += "{0}".format(self._columnHeaders[-1][0])
            return str
