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


from datatypes.Enums import EnumParserColumns, EnumTimeParts

class FileNameSchema(object):
    """ Basic support class which encodes and decodes strings (specifically filenames) given their schema.
        The supported schema is as follows:
           +%f  flake id
           +%c  camera id
           +%d  date (yyyy.mm.dd)       %Y - year, %M - month,  %D - day
           +%T  time (hh.mm.ss)         %h - hour, %m - minute, %s - second, %u - microseconds

        NOTE: for some types of files, some of these elements may not make sense. For example,
              the highest time resolution for an output folder should be hours, rather than seconds.
              Hence it would not make sense to include %T within its naming schema

        Data encoded and decoded using dictionaries with the following naming convention:
           %f - 'flakeId'
           %c - 'cameraId'
           %d -> converted into components: %Y - 'year', %M - 'month, %D - 'day'
           %T -> converted into components: %h - 'hour', %m - 'minute', %s - 'second', %u - 'microsecond'
    """

    # All possible delimiters we can parse, with corresponding dictionary keys and correct
    # length data must take. The length is used when we have multiple delimiters back to back
    # like %d%u. However, delimiter length None indicates unlimited length
    # TODO: abstract away the string names so we can easily change them later if needed
    _delimiterTranslationTable = {
        "f": (EnumParserColumns.FLAKE_ID,  None),
        "c": (EnumParserColumns.CAMERA_ID, None),
        # We translate %d into %Y.%M.%D, so there is no d delimiter
        "Y": (EnumTimeParts.YEAR,  4),
        "M": (EnumTimeParts.MONTH, 2),
        "D": (EnumTimeParts.DAY,   2),
        # We translate %T into %h.%m.%d, so there is no %T delimiter
        "h": (EnumTimeParts.HOUR,   2),
        "m": (EnumTimeParts.MINUTE, 2),
        "s": (EnumTimeParts.SECOND, 2),
        "u": (EnumTimeParts.MICROSECOND, 6),
    }

    def __init__(self, schema):
        """ Initializes object given input schema. The format is described in the help for the class

            :param schema: string
        """
        # String which signifies our schema
        self._schemaString = ''

        # Helper list of delimiters which will be used to break schema apart into separate pieces
        self._delimiterList = []

        # The first bunch of letters before the very first delimiter. If empty, then
        # we started with a delimiter
        # TODO: might be interesting to add this into the _delimiterList because parsing it out can be handled similarly to delimiters
        self._beginWith = ''

        # Note: we will cheat a little to simplify parsing date and time
        self._schemaString = schema.replace("%d", "%Y.%M.%D")
        self._schemaString = self._schemaString.replace("%T", "%h.%m.%s")

        # check if we start with a delimiter
        startWithDelimiter = (self._schemaString[0] == '%')

        # build up the list of delimiters
        splitVals = self._schemaString.split('%')

        # If we don't start with a delimiter, then we need to store
        # what string we rip out in the beginning
        if not startWithDelimiter:
            self._beginWith = splitVals[0]
        splitVals = splitVals[1:]

#        print self.schemaString
#        print splitVals
#        print self._beginWith

        # Based on the first character of the next split value, we know what
        # what schema variable we had
        for s in splitVals:
            delimeter  = s[0]
            rightSplit = s[1:]
            self._delimiterList.append([self._delimiterTranslationTable[delimeter], rightSplit])


    def Encode(self, schemaDataDict):
        """ Encodes a given date/time into a string using our schema.

            :param schemaDataDict: input date and time as a dictionary described in help
            :return: string
        """
        outStr = self._schemaString
        for delim in self._delimiterTranslationTable:
            name, nameLen = self._delimiterTranslationTable[delim]
            if name in schemaDataDict:
                val = int(schemaDataDict[name])
                tagToReplace = "%{0}".format(delim)
                # get string with leading 0s where it matters
                if delim == 'Y':
                    strRepl = "{0:04d}".format(val)
                elif delim == 'M' or \
                     delim == 'D' or \
                     delim == 'h' or \
                     delim == 'm' or \
                     delim == 's':
                    strRepl = "{0:02d}".format(val)
                elif delim == 'u':
                    strRepl = "{0:06d}".format(val)
                else:
                    strRepl = "{0}".format(val)
                outStr = outStr.replace(tagToReplace, strRepl)
        return outStr


    def Decode(self, inString):
        """ Decodes a string that should match the schema into a dictionary of elements.
            Any element that's unknown will be returned as None. Returns None on error
            (as in when string does not match)

            :param inString: input string to decode
            :return: dictionary with date/time elements
        """
        # Main idea is to chip away at the string front to back
        # note that we can not resolve things like snowflake and camera id

        # default returns are None for each element
        valsToRet = {}
        for d in self._delimiterTranslationTable:
            delimName = self._delimiterTranslationTable[d]
            valsToRet[delimName[0]] = None

        # check we start correctly
        startWith = inString[0:len(self._beginWith)]
        if not startWith == self._beginWith:
            return None

        inString = inString[len(self._beginWith):]

        # Run through all delimiters in order and try to rip pieces out
        for delim in self._delimiterList:
            delimName = delim[0][0]
            delimLen  = delim[0][1]
            delimNext = delim[1]

            # not enough length - we're done
            if delimLen is not None and len(inString) < delimLen:
                break

            # Try to grab the next element given length. Otherwise, try to read up to separator following
            # Also trim the string down
            nextStr = None
            if delimLen is not None:
                # we might have specified a separator until the next delimiter
                if len(delimNext) > 0:
                    nextLoc  = inString.find(delimNext)
                    nextStr  = inString[0:nextLoc]
                    inString = inString[nextLoc + len(delimNext):]
                # if empty read the full length we can
                else:
                    nextStr  = inString[0:delimLen]
                    inString = inString[delimLen:]
            # if delimiter length is None, this token has no set length (like flake id). Try to read
            # until the splitter first. If not, assume we have to read until the end
            else:
                if len(delimNext) > 0:
                    nextLoc  = inString.find(delimNext)
                    nextStr  = inString[0:nextLoc]
                    inString = inString[nextLoc + len(delimNext):]
                else:
                    nextStr  = inString
                    inString = ''

            # assign to dictionary entry as an integer
            try:
                valsToRet[delimName] = int(nextStr)
            except Exception as e:
                return None

        if len(inString) > 0:
            return None

        # done
        return valsToRet


    def Print(self, stringPrepend = ""):
        """ Basic print function using print

            :param stringPrepend: prepended before each print statement. Intended for spaces
        """
        print "{0}- schema:     \"{1}\"".format(stringPrepend, self._schemaString)
        print "{0}- begin with: \"{1}\"".format(stringPrepend, self._beginWith)
        print "{0}- delimiters: \"{1}\"".format(stringPrepend, self._delimiterList)



def FunctionalTest():
    """ Performs a basic functional test for this module. Prints results to std.
    """
    print "---------------------------------"
    print "Running a test on {0}".format(__file__)

    # help identify names of dictionary items
    nameSchema       = 'schema'
    nameStart        = 'start'
    nameDelimiters   = 'delimeters'
    nameEncodeData   = 'encodeData'
    nameEncodeString = 'encodeString'
    nameSkipEncode   = 'skipEncode'

    # full test description
    testParams = [
        {
            nameSchema : 'masc_%d_Hr_%h',
            nameStart : 'masc_',
            nameDelimiters : [[EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '_Hr_'],
                              [EnumTimeParts.HOUR, '']],
            nameEncodeData : {EnumTimeParts.YEAR: 2015,
                              EnumTimeParts.MONTH: 1,
                              EnumTimeParts.DAY: 4,
                              EnumTimeParts.HOUR: 19},
            nameEncodeString : 'masc_2015.01.04_Hr_19',
            nameSkipEncode : False,
        },
        {
            nameSchema : '%umasc_%d_Hr_%habc',
            nameStart : '',
            nameDelimiters : [[EnumTimeParts.MICROSECOND, 'masc_'],
                              [EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '_Hr_'],
                              [EnumTimeParts.HOUR, 'abc']],
            nameEncodeData : {EnumTimeParts.MICROSECOND: 123456,
                              EnumTimeParts.YEAR: 2015,
                              EnumTimeParts.MONTH: 1,
                              EnumTimeParts.DAY: 4,
                              EnumTimeParts.HOUR: 19},
            nameEncodeString : '123456masc_2015.01.04_Hr_19abc',
            nameSkipEncode : False,
        },
        {
            nameSchema : '%Y%M%D%h%m%s%u',
            nameStart : '',
            nameDelimiters : [[EnumTimeParts.YEAR, ''],
                              [EnumTimeParts.MONTH, ''],
                              [EnumTimeParts.DAY, ''],
                              [EnumTimeParts.HOUR, ''],
                              [EnumTimeParts.MINUTE, ''],
                              [EnumTimeParts.SECOND, ''],
                              [EnumTimeParts.MICROSECOND, '']],
            nameEncodeData : {EnumTimeParts.YEAR: 2015,
                              EnumTimeParts.MONTH: 1,
                              EnumTimeParts.DAY: 4,
                              EnumTimeParts.HOUR: 19,
                              EnumTimeParts.MINUTE: 5,
                              EnumTimeParts.SECOND: 3,
                              EnumTimeParts.MICROSECOND: 123456},
            nameEncodeString : '20150104190503123456',
            nameSkipEncode : False,
        },
        {
            nameSchema : 'some/path/dataFolder_%d/hourFolder%h/masc%D_file%f.%c',
            nameStart : 'some/path/dataFolder_',
            nameDelimiters : [[EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '/hourFolder'],
                              [EnumTimeParts.HOUR, '/masc'],
                              [EnumTimeParts.DAY, '_file'],
                              [EnumParserColumns.FLAKE_ID, '.'],
                              [EnumParserColumns.CAMERA_ID, '']],
            nameEncodeData : {EnumTimeParts.YEAR: 2015,
                              EnumTimeParts.MONTH: 1,
                              EnumTimeParts.DAY: 4,
                              EnumTimeParts.HOUR: 19,
                              EnumParserColumns.FLAKE_ID: 1000,
                              EnumParserColumns.CAMERA_ID: 8},
            nameEncodeString : 'some/path/dataFolder_2015.01.04/hourFolder19/masc04_file1000.8',
            nameSkipEncode : False,
        },
        {
            nameSchema : 'masc_%d_Hr_%h',
            nameStart : 'masc_',
            nameDelimiters : [[EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '_Hr_'],
                              [EnumTimeParts.HOUR, '']],
            nameEncodeData : None,
            nameEncodeString : 'mascXX_2015.01.04_Hr_19',
            nameSkipEncode : True,
        },
        {
            nameSchema : 'masc_%d_Hr_%h',
            nameStart : 'masc_',
            nameDelimiters : [[EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '_Hr_'],
                              [EnumTimeParts.HOUR, '']],
            nameEncodeData : None,
            nameEncodeString : 'masc_2015.01.04_XXHr_19',
            nameSkipEncode : True,
        },
        {
            nameSchema : 'masc_%d_Hr_%h',
            nameStart : 'masc_',
            nameDelimiters : [[EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '_Hr_'],
                              [EnumTimeParts.HOUR, '']],
            nameEncodeData : None,
            nameEncodeString : 'masc_XX2015.01.04_Hr_19',
            nameSkipEncode : True,
        },
        {
            nameSchema : 'masc_%d_Hr_%h',
            nameStart : 'masc_',
            nameDelimiters : [[EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '_Hr_'],
                              [EnumTimeParts.HOUR, '']],
            nameEncodeData : None,
            nameEncodeString : 'masc_2015XX.01.04_Hr_19',
            nameSkipEncode : True,
        },
        {
            nameSchema : 'masc_%d_Hr_%h',
            nameStart : 'masc_',
            nameDelimiters : [[EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '_Hr_'],
                              [EnumTimeParts.HOUR, '']],
            nameEncodeData : None,
            nameEncodeString : 'masc_2015.01.04_Hr_19XX',
            nameSkipEncode : True,
        },
        {
            nameSchema : 'some/path/dataFolder_%d/hourFolder%h/masc%D_file%f.%c',
            nameStart : 'some/path/dataFolder_',
            nameDelimiters : [[EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '/hourFolder'],
                              [EnumTimeParts.HOUR, '/masc'],
                              [EnumTimeParts.DAY, '_file'],
                              [EnumParserColumns.FLAKE_ID, '.'],
                              [EnumParserColumns.CAMERA_ID, '']],
            nameEncodeData : None,
            nameEncodeString : 'some/path/dataFolder_2015.01.04/hourFolder19/masc04_file1000.8XX',
            nameSkipEncode : True,
        },
        {
            nameSchema : 'some/path/dataFolder_%d/hourFolder%h/masc%D_file%f.%c',
            nameStart : 'some/path/dataFolder_',
            nameDelimiters : [[EnumTimeParts.YEAR, '.'],
                              [EnumTimeParts.MONTH, '.'],
                              [EnumTimeParts.DAY, '/hourFolder'],
                              [EnumTimeParts.HOUR, '/masc'],
                              [EnumTimeParts.DAY, '_file'],
                              [EnumParserColumns.FLAKE_ID, '.'],
                              [EnumParserColumns.CAMERA_ID, '']],
            nameEncodeData : None,
            nameEncodeString : 'some/path/dataFolder_2015.01.04/hourFolder19/masc04_file1000XX.8',
            nameSkipEncode : True,
        },
    ]

    allPassed = True
    for t in testParams:
        print "\n>>> Testing string: \"{0}\" <<<".format(t[nameSchema])
        success = True
        t1 = FileNameSchema(t[nameSchema])
        if not t[nameSkipEncode]:
            t1Str = t1.Encode(t[nameEncodeData])
        else:
            t1Str = None

        # check start
        success &= (t1._beginWith == t[nameStart])

        # check all delimiters
        for data, test in zip(t1._delimiterList, t[nameDelimiters]):
            success &= (data[0][0] == test[0])
            success &= (data[1] == test[1])
#            print "    data: {0}, test: {1}".format(data, test)

        # check encoded string
        if not t[nameSkipEncode]:
            success &= (t1Str == t[nameEncodeString])

        # check decoding
        decodeDict = t1.Decode(t[nameEncodeString])
        print "decoded: {0}".format(decodeDict)
        if decodeDict is None:
            success &= (decodeDict == t[nameEncodeData])
        elif t[nameEncodeData] is None:
            success = False
        else:
            for d in decodeDict:
                decodeVal = decodeDict[d]

                # We expect None for anything that isn't part of t[nameDelimiters]
                if decodeVal is None:
                    success &= (d not in t[nameDelimiters])
                # otherwise, our values should match
                else:
                    success &= (t[nameEncodeData][d] == decodeVal)


        # How well did we do?
        # TODO: perhaps introduce the notion of expected failure for these tests
        if success:
            print "  pass"
            t1.Print("    ")
        else:
            print "  fail."
            print "    - start: \"{0}\", got: \"{1}\"".format(t[nameStart], t1._beginWith)
            print "    - delimiters:"
            for data, test in zip(t1._delimiterList, t[nameDelimiters]):
                print "      \"{0}\", got: \"{1}\"".format(test, data)
            print "    - encoded: \"{0}\", got: \"{1}\"".format(t[nameEncodeString], t1Str)
            print "    - decoded: \"{0}\"".format(decodeDict)

        allPassed &= success

    print "\n---------------------------------"
    print "all tests passed? {0}".format(allPassed)

if __name__ == '__main__':
    FunctionalTest()
