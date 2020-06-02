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

from datetime import datetime
from Enums import EnumTimeParts

class Timestamp(object):
    """ Helper class to convert string representations of dates and times into Python's internal representation.
    """

    def __init__(self):
        """ By default, we create an empty object. Using it should result in errors
        """
        self.dateStr = ""
        self.timeStr = ""
        self.dateTime = None


    def FromStrings(self, dateStr, timeStr):
        """ Basic initialization of the date/time structure. Also keeps track of the original strings that
            initialized this element.

            :param dateStr: date string formatted as (mm.dd.yyyy)
            :param timeStr: time string formatted as (hh:mm:ss.mmmmmm)
        """
        # string for date in format (mm.dd.yyyy)
        self.dateStr = dateStr

        # string for time in format (hh:mm:ss.mmmmmm)
        self.timeStr = timeStr

        # converted date-time
        self.dateTime  = datetime.strptime("{0} {1}".format(dateStr, timeStr), "%m.%d.%Y %H:%M:%S.%f")


    def FromDateTime(self, dateTimeObj):
        """ Basic initialization of the date/time structure. Generates and keeps strings for date and time

            :param dateTimeObj: datetime object
        """
        # copy date/time over
        self.dateTime = dateTimeObj

        # generate the date string with format (mm.dd.yyyy)
        self.dateStr = self.dateTime.strftime("%m.%d.%Y")

        # generate the time string with format (hh:mm:ss.mmmmmm)
        self.timeStr = self.dateTime.strftime("%H:%M:%S.%f")


    def GetComponents(self):
        """ Gets individual components making up a date/time stamp

            :return: dictionary of components
        """
        toRet = {
            EnumTimeParts.YEAR        : self.dateTime.year,
            EnumTimeParts.MONTH       : self.dateTime.month,
            EnumTimeParts.DAY         : self.dateTime.day,
            EnumTimeParts.HOUR        : self.dateTime.hour,
            EnumTimeParts.MINUTE      : self.dateTime.minute,
            EnumTimeParts.SECOND      : self.dateTime.second,
            EnumTimeParts.MICROSECOND : self.dateTime.microsecond
        }
        return toRet


    def IsOutisdeRange(self, fromDate, toDate):
        """ Checks whether the time held by this structure is outside of a given time range [fromDate, toDate]
            inclusive

            :param fromDate: start of the range, must be Timestamp object
            :param toDate: end of the range, must be Timestamp object
            :return: bolean flag
        """
        return self.dateTime < fromDate.dateTime or \
               self.dateTime > toDate.dateTime


    def Print(self, stringPrepend = ''):
        """ Simple print function

            :param stringPrepend: string to prepend for each print call (intended for spaces)
        """
        print "{0} - date captured:  \"{1}\" (mm.dd.yyyy)".format(stringPrepend, self.dateStr)
        print "{0} - time captured:  \"{1}\" (hh:mm:ss.mmmmmm)".format(stringPrepend, self.timeStr)


    @staticmethod
    def PrintAsNone(stringPrepend = ''):
        """ Simple print function when object is of NoneType

            :param stringPrepend: string to prepend for each print call (intended for spaces)
        """
        print "{0} - date captured:  \"None\" (mm.dd.yyyy)".format(stringPrepend)
        print "{0} - time captured:  \"None\" (hh:mm:ss.mmmmmm)".format(stringPrepend)
