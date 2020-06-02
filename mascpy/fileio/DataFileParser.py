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


"""
Parses the image and fallspeed data files output by the MASC.

-- Image Output --
Each file stores image information corresponding to the hydrometeor that was captured.
Implemented using ImageDataParser() class

File format example:
flake ID	camera ID	date (mm.dd.yyyy)	time (hh:mm:ss.mmmmmm)	image name	frame timestamp
1	2	06.03.2015	20:05:53.209534	2015.06.03_20.05.53_flake_1_cam_2.png	0

The first few lines are reserved for a header. This header is entirely optional and can contain some
paragraph-like text describing what to expect within the file. Typical header would include column descriptions.

All data that follows is a tab-delimited ASCII format. Each column (left to right)
 - flake id               - numeric value that is the id of the particle that we captured
                            NOTE: if data acquisition was restarted, several particles will share this id, however
                                  they are guaranteed to have different time stamps
 - camera id              - numeric value for the id of the camera that took this image. The first camera is 0
 - date (mm.dd.yyyy)      - date when this particle was captured. The format is shown within the parenthesis.
                            Format: mm   - 2 digit month. 01 = January, 12 = December
                                    dd   - 2 digit day. Range: 01 - 31
                                    yyyy - 4 digit year.
 - time (hh:mm:ss.mmmmmm) - timestamp when the image was captured. The format is shown within the paranthesis.
                            Format: hh     - 2 digit hour. 00 = midnight, 11 = 11am, 23 - 11pm
                                    mm     - 2 digit minute. Range: 00 - 59
                                    ss     - 2 digit second. Range: 00 - 59
                                    mmmmmm - 6 digits for microseconds.
                            NOTE: this timestamp should _not_ be used as the identification of when the hydrometeor
                                  was captured. Use the fallspeed data file as it should be more accurate. The
                                  difference in time in actuality is on the order of a second.
                            NOTE: The time when the image was created (as told by the file system) may be significantly
                                  different from the actual capture time.
 - image name             - filename of the saved image.
                            NOTE: Unfortunately the path to the image relative to the data file is not saved. This
                                  typically is not an issue when both images and data files are contained within the
                                  same directory.
                            NOTE: Another gotcha: depending on the specific timing, images for the same hydrometeor
                                  can span across time boundary (say hour) and could result in eing saved into
                                  different subfolders and data files. Therefore it's best to aggregate this data
                                  before processing.
 - frame timestamp        - deprecated


-- Fallspeed Output --
Each file stores fallspeed information corresponding to the hydrometeor that was captured.
Implemented using FallspeedDataParser() class

File format example:
snowflake id	date (mm.dd.yyyy)	time (hh:mm:ss.mmmmmm)	fall speed (m/s)
80516	04.02.2013	03:00:05.279664	0.0966482

The format is very similar to the image format along with restrictions of how the file is stored. The only addition
is the "fall speed (m/s)" column, which shows fall speed for the hydrometeor as captured by the MASC. The value is
a floating point number.
"""

from datatypes.Enums import EnumParserColumns, EnumRawDataType


class TabulatedParserBase(object):
    """ Base class which will read tabulated ASCII data files with multiple columns. For details on
        how to specify data and such, please see help for the DataFileParser package.
    """

    # Each derived class must define column specification, which shows order in the ASCII file and
    # corresponding dictionary key when values are returned. Each entry is an array of data:
    # [<type = int, float, string>, 'output name']
    _columnOrder = []


    def ParseString(self, inString):
        """ Parses a given string as read from a file. Assumes an ASCII string where each row of
            data is separated by a newline character, and each column is split with a tab.
            The result is an array of dictionaries in order they were read within the file.
            If no data was read, returns an empty array.

            :param inString: ASCII string full of data
            :return: array of dicts with data, each made up according to self._columnOrder
        """
        toReturn = []

        # Iterate through the string using rather than generating a huge array. This will be helpful for
        # extremely large files where the latter will be memory prohibitive.
        for lineStr in iter(inString.splitlines()):
            result = self._ParseLineString(lineStr)
            if result is not None:
                toReturn.append(result)

        return toReturn


    def ParseFile(self, inFileName):
        """ Similar to ParseString(...) function. Parses a file line by line instead of a string.
            The file is specified by the path and is assumed to be in ASCII format. If the file
            doesn't exist or is empty of data, function returns an empty array.

            :param inFileName: file name of the file to read. Assumes ASCII
            :return: array of dicts with data, each made up according to self._columnOrder
        """
        try:
            with open(inFileName, 'r') as f:
                toReturn = []
                for lineStr in f:
                    result = self._ParseLineString(lineStr)
                    if result is not None:
                        toReturn.append(result)
                return toReturn
        except IOError:
            return []


    #
    # Helpers - should not be called directly
    #
    def _ParseLineString(self, inString):
        """ Parses the string which represents a single line in the file. This way we will be able to process both
            strings and full files (read line by line for perf reasons). The function returns a dictionary with
            all of our data. If the string starts with a non-integral type, it assumes that this string is a comment.

            :param inString: string (can end with newline) for a line if data
            :return: None is empty or not enough data. Otherwise, dict with data as specified by self._columnOrder
        """
        # clean up the string before splitting it
        inString = inString.strip(' \r\n')
        columns = inString.split('\t')

        # error when fewer columns than needed
        if len(columns) < len(self._columnOrder):
            return None

        # in case our comment somehow contained delimiters, double check that the first item is numeric
        if not columns[0].isdigit():
            return None

        # run through each column, converting it to correct data type and putting it into a dictionary to be returned
        dataToRet = {}
        for colData, colName in zip(columns, self._columnOrder):
            convData = None
            if colName[0] == EnumRawDataType.INT:
                convData = int(colData)
            elif colName[0] == EnumRawDataType.FLOAT:
                convData = float(colData)
            else:
                convData = colData

            dataToRet[colName[1]] = convData

        return dataToRet


class ImageDataParser(TabulatedParserBase):
    """ Parser specialization for the image file parser. All parsing work is handled by the base class.
        Please see help for TabulatedParserBase() class for more details
    """
    def __init__(self):
        # Specify column order
        self._columnOrder = [
            [EnumRawDataType.INT,    EnumParserColumns.FLAKE_ID],
            [EnumRawDataType.INT,    EnumParserColumns.CAMERA_ID],
            [EnumRawDataType.STRING, EnumParserColumns.DATE_STR],
            [EnumRawDataType.STRING, EnumParserColumns.TIME_STR],
            [EnumRawDataType.STRING, EnumParserColumns.IMAGE_NAME_STR],
            [EnumRawDataType.STRING, EnumParserColumns.FRAME_TIME_STAMP_STR]
        ]


class FallspeedDataParser(TabulatedParserBase):
    """ Parser specialization for the fall speed data file parser. All parsing work is handled by the base class.
        Please see help for TabulatedParserBase() class for more details
    """
    def __init__(self):
        # Specify column order
        self._columnOrder = [
            [EnumRawDataType.INT,    EnumParserColumns.FLAKE_ID],
            [EnumRawDataType.STRING, EnumParserColumns.DATE_STR],
            [EnumRawDataType.STRING, EnumParserColumns.TIME_STR],
            [EnumRawDataType.FLOAT,  EnumParserColumns.FALL_SPEED]
        ]




def CompareResults(testDesc, testString, expResult, isMultiline, gotResult):
    """ Small functional test helper to compare returned data against expected

        :param testDesc: string description of the test to be printed
        :param testString: input string to be parsed (single or multiline)
        :param expResult: expected result to compare against (dict or array of dicts)
        :param isMultiline: flag if expected result is an array
        :param gotResult: what result did we actually compute to check for correctness
        :return: if test has passed (actual result matches what is expected)
    """
    testStrEscaped = testString.replace('\n', '\\n')
    testStrEscaped = testStrEscaped.replace('\t', '\\t')
    testStrEscaped = testStrEscaped.replace('\r', '')

    print "\n>>> Test description: \"{0}\" <<<".format(testDesc)
    success = True
#    print "    - input string: \"{0}\"".format(testStrEscaped)
#    print "    - result:       \"{0}\"".format(gotResult)

    # small helper to check for correctness one dictionary at a time
    def compareDicts(expected, result):
        toRet = True
        if expected is None:
            toRet = (result is None)
        elif expected is []:
            toRet = (result == [])
        elif result is None:
            toRet = False
        else:
            # TODO: abstract away dictionary comparison for tests... Could Mocking help here?
            # Expected and returned dicts must match exactly (no missing or extra elements, test against None)
            for r in expected:
                toRet &= (expected[r] == result[r])
        return toRet

    # compare what we got with what's expected
    if isMultiline:
        for expRow, gotRow in zip(expResult, gotResult):
            success &= compareDicts(expRow, gotRow)
        success &= (len(expResult) == len(gotResult))
    else:
        success = compareDicts(expResult, gotResult)

    # How well did we do?
    if success:
        print "  pass"
    else:
        print "  fail"
        print "    - expected: \"{0}\"".format(expResult)
        print "    - computed: \"{0}\"".format(gotResult)

    return success


def FunctionalTestImages():
    """ Functional test for image parser. This also tests the base class thoroughly, to make
        fallspeed data parser testing weigh much less.
        :return: if tests pass
    """
    # help identify names of dictionary items
    nameTestDesc = 'testDesc'
    nameString = 'inString'
    nameIsArray = 'isArray'
    nameExpResult = 'expResult'

    # some common pieces of data
    colHeader = 'flake ID	camera ID	date (mm.dd.yyyy)	time (hh:mm:ss.mmmmmm)	image name	frame timestamp\n'
    comment = 'Some comment\n'
    data0Str = '1	2	06.03.2015	20:05:53.209534	2015.06.03_20.05.53_flake_1_cam_2.png	0\n'
    data0Dict = {EnumParserColumns.FLAKE_ID: 1,
                 EnumParserColumns.CAMERA_ID: 2,
                 EnumParserColumns.DATE_STR: '06.03.2015',
                 EnumParserColumns.TIME_STR: '20:05:53.209534',
                 EnumParserColumns.IMAGE_NAME_STR: '2015.06.03_20.05.53_flake_1_cam_2.png',
                 EnumParserColumns.FRAME_TIME_STAMP_STR: '0'}
    data1Str = '80516	1	04.02.2013	03:00:05.083653	2013.04.02_03.00.05.083653_flake_80516_cam_1.png	0\n'
    data1Dict = {EnumParserColumns.FLAKE_ID: 80516,
                 EnumParserColumns.CAMERA_ID: 1,
                 EnumParserColumns.DATE_STR: '04.02.2013',
                 EnumParserColumns.TIME_STR: '03:00:05.083653',
                 EnumParserColumns.IMAGE_NAME_STR: '2013.04.02_03.00.05.083653_flake_80516_cam_1.png',
                 EnumParserColumns.FRAME_TIME_STAMP_STR: '0'}

    data0StrBad = '\t'.join(data0Str.split('\t')[0:-1]) + '\n'
    data1StrBad = '\t'.join(data1Str.split('\t')[0:-1]) + '\n'

    # Test data with expected outcomes
    imageTest = [
        {
            nameTestDesc : 'fully formed column titles',
            nameString : colHeader,
            nameExpResult : None,
            nameIsArray : False,
        },
        {
            nameTestDesc : 'fully formed data string',
            nameString : data0Str,
            nameExpResult : data0Dict,
            nameIsArray : False,
        },
        {
            nameTestDesc : 'incomplete data string',
            nameString : '1	2',
            nameExpResult : None,
            nameIsArray : False,
        },
        {
            nameTestDesc : 'empty string',
            nameString : '',
            nameExpResult : None,
            nameIsArray : False,
        },
        {
            nameTestDesc : 'multiline full header',
            nameString : comment + colHeader + data1Str,
            nameExpResult : [data1Dict],
            nameIsArray : True,
        },
        {
            nameTestDesc : 'multiline comment and one data',
            nameString : comment + data1Str,
            nameExpResult : [data1Dict],
            nameIsArray : True,
        },
        {
            nameTestDesc : 'multiline just one data',
            nameString : data1Str,
            nameExpResult : [data1Dict],
            nameIsArray : True,
        },
        {
            nameTestDesc : 'multiline full header and two good data',
            nameString : colHeader + data0Str + data1Str,
            nameExpResult : [data0Dict, data1Dict],
            nameIsArray : True,
        },
        {
            nameTestDesc : 'multiline column header, missing one column several data',
            nameString : colHeader + data0StrBad + data1StrBad,
            nameExpResult : [],
            nameIsArray : True,
        },
        {
            nameTestDesc : 'multiline column header, one data row missing column',
            nameString : colHeader + data0StrBad + data1Str,
            nameExpResult : [data1Dict],
            nameIsArray : True,
        },
    ]

    print "Testing image parser"
    imgParser = ImageDataParser()
    allPassed = True

    for t in imageTest:
        if t[nameIsArray]:
            result = imgParser.ParseString(t[nameString])
        else:
            result = imgParser._ParseLineString(t[nameString])
        allPassed &= CompareResults(t[nameTestDesc], t[nameString], t[nameExpResult], t[nameIsArray], result)

    # final see if we can parse some file
    filePath = '../data/imgInfo_2015.06.03_20_05.txt'
    print ">>> Reading a file: \"{0}\" (doesn't exist) <<<".format(filePath)
    result = imgParser.ParseFile(filePath)
    allPassed &= (result == [])
    if result == []:
        print "  pass"
    else:
        print "  fail"
        print "  got: \"{0}\"".format(result)

    # existing file
    print ">>> Reading a file \"{0}\" (exists) <<<".format('../' + filePath)
    result = imgParser.ParseFile('../' + filePath)
    allPassed &= (not result == [])
    if not result == []:
        print "  pass"
    else:
        print "  fail"
        print "  got: \"{0}\"".format(result)

    return allPassed


def FunctionalTestFallspeed():
    """ Functional test for fallspeed parser. This tests just simple functionality relevant to
        fallspeed data files, because it assumes full testing is done by image file test.

        :return: if tets pass
    """
    # help identify names of dictionary items
    nameTestDesc = 'testDesc'
    nameString = 'inString'
    nameIsArray = 'isArray'
    nameExpResult = 'expResult'

    # Test data with expected outcomes
    fallTest = [
        {
            nameTestDesc : 'fully formed column titles',
            nameString : 'snowflake id	date (mm.dd.yyyy)	time (hh:mm:ss.mmmmmm)	fall speed (m/s)\n',
            nameExpResult : None,
            nameIsArray : False,
        },
        {
            nameTestDesc : 'fully formed data string',
            nameString : '80516	04.02.2013	03:00:05.279664	0.0966482\n',
            nameExpResult : {EnumParserColumns.FLAKE_ID: 80516,
                             EnumParserColumns.DATE_STR: '04.02.2013',
                             EnumParserColumns.TIME_STR: '03:00:05.279664',
                             EnumParserColumns.FALL_SPEED: 0.0966482},
            nameIsArray : False,
        },

        # Note: no need to test things like handling multiple headers, and incomplete columns
        # because the image test covers this case
    ]

    print "Testing fallspeed parser"
    fallParser = FallspeedDataParser()
    allPassed = True

    for t in fallTest:
        if not t[nameIsArray]:
            result = fallParser._ParseLineString(t[nameString])
            allPassed &= CompareResults(t[nameTestDesc], t[nameString], t[nameExpResult], t[nameIsArray], result)

    return allPassed


def FunctionalTest():
    """ Main functional test that calls both image and fallspeed functional tests
    """
    # TODO: test data and image parsing from strings with following parameters
    # 1. full header, column header, or no header
    # 2. incomplete images (say 2 of 3)
    # 3. incompletely written (just header, totally empty, missing some number of columns at the end:
    #    whole file and last line)
    # 4. throw in some NaNs or Infs or negs?

    print "---------------------------------"
    print "Running a test on {0}".format(__file__)
    allPassed = True

    allPassed &= FunctionalTestImages()

    print "\n---------------------------------"
    allPassed &= FunctionalTestFallspeed()

    print "\n---------------------------------"
    print "all tests passed? {0}".format(allPassed)

if __name__ == '__main__':
    FunctionalTest()
