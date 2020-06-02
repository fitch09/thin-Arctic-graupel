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


from enum import Enum


class EnumRawDataType(Enum):
    """ Helper to define data types for the parsers, intended to be applied to ASCII file columns
    """
    INT    = 0
    FLOAT  = 1
    STRING = 2

class EnumParserColumns(Enum):
    """ Helper to define the names of each column in the data files. String versions can be:
        - flakeId
        - cameraId
        - date
        - time
        - imageName
        - frameTimeStamp
        - fallSpeed
    """
    FLAKE_ID             = 0
    CAMERA_ID            = 1
    DATE_STR             = 2
    TIME_STR             = 3
    IMAGE_NAME_STR       = 4
    FRAME_TIME_STAMP_STR = 5
    FALL_SPEED           = 6

class EnumTimeParts(Enum):
    """ Helper to identify pieces making up date and times. String versions can be:
        - year
        - month
        - day
        - hour
        - minute
        - second
        - microsecond
    """
    YEAR        = 0
    MONTH       = 1
    DAY         = 2
    HOUR        = 3
    MINUTE      = 4
    SECOND      = 5
    MICROSECOND = 6

class EnumParameterType(Enum):
    """ Helper to identify pieces useful for analysis or acquisition parameters (there's an overlap).
    """
    CROP_TOP            = 0
    CROP_BOTTOM         = 1
    CROP_LEFT           = 2
    CROP_RIGHT          = 3
    CAM_HORIZ_FOV_IN_UM = 4
