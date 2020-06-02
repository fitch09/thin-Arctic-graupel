#! /apps/base/python2.7/bin/python
#*******************************************************************************
#  Author:
#     name:  
#     phone: 
#     email: 
#*******************************************************************************
#  REPOSITORY INFORMATION:
#    $Revision: 74177 $
#    $Author: shkurko $
#    $Date: 2016-10-11 21:46:26 +0000 (Tue, 11 Oct 2016) $
#    $State: $
#*******************************************************************************

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


import sys
import os
import string
import time
import datetime
import calendar
import copy
import json
import math
import timeit
import traceback
sys.path.append(os.environ['VAP_HOME'] + '/lib/masc_flake_anal')
import cds3 as cds
import dsproc3 as dsproc

flagEnableProfile = False

if flagEnableProfile:
    import cProfile, pstats, StringIO

# load MASC VAP library
sys.path.append('/apps/base/lib/python2.7/site-packages')       # OpenCV2
from Enums               import EnumParserColumns
from FlakeInfo           import FlakeInfo
from ImageAnalyzer       import ImageAnalyzer
from ParticleAnalyzer    import ParticleAnalyzer
from TimeSeriesGenerator import TimeSeriesGenerator
from DataAnalysisConfig  import DataAnalysisConfig

# Needed to run locally it seems (on research machine)
#from masc_flake_anal.Enums               import EnumParserColumns
#from masc_flake_anal.FlakeInfo           import FlakeInfo
#from masc_flake_anal.ImageAnalyzer       import ImageAnalyzer
#from masc_flake_anal.ParticleAnalyzer    import ParticleAnalyzer
#from masc_flake_anal.TimeSeriesGenerator import TimeSeriesGenerator
#from masc_flake_anal.DataAnalysisConfig  import DataAnalysisConfig

MASC_CONFIG_FILE          = os.getenv('VAP_HOME') + '/conf/vap/masc_flake_anal/defImgAnlParams.json'

MASC_A1_B1_DS_NAME        = "masc"

MASC_C1_DS_NAME_PARTICLES = "mascparticles"
MASC_C1_DS_NAME_TIME_BINS = "mascparticlesavg"
MASC_C1_DS_LEVEL          = "c1"

MISSING_VALUE             = -9999

class UserData(object):
    def __init__(self, proc_name):
        self.proc_name = proc_name


class InDataVarGetter(object):
    """ Helps associate variable name in datastream within input masc.b1 datastream. Helps abstract variable gather
        and returning any errors during fetching variable or its index
    """
    def __init__(self, var_name, has_qc_var):
        # variable name as string
        self.var_name = var_name

        # flag whether this variable has a qc variable associated
        self.has_qc_var = has_qc_var


class OutDataVarHelper(object):
    """ Helps associate variable name in datastream within output, either mascparticles.c1 or masctimebins.c1. Helps
        abstract variable gather and returning any errors during fetching variable or its index
    """
    def __init__(self, var_name, has_qc_var, can_eq_missing, is_aggregate, dim_size1, dim_size2):
        # string name for the variable stored within datastream
        self.var_name = var_name

        # flag whether variable has an associated QC variable, assumed to be named 'qc_<var_name>'
        self.has_qc_var = has_qc_var

        # flag whether data can be set to MISSING_VALUE
        self.can_eq_missing = can_eq_missing

        # flag whether data is aggregate. This affects how data here is set to MISSING_VALUE
        self.is_aggregate = is_aggregate

        # dimensionality of the data beyond time (0 = off)
        self.dim_size1 = dim_size1
        self.dim_size2 = dim_size2


class DataVarPtrs(object):
    """ Container for data pointers to ease accessing both data and associated qc params.
        Meant to be used with a map, like 'var name' -> this struct. QC parameter can be None
    """
    def __init__(self, var_ptr, qc_var_ptr):
        self.var_ptr    = var_ptr
        self.qc_var_ptr = qc_var_ptr

gVersion = "$State:$"



class StatusPrinter(object):
    """ Helper wrapper for all status output through dsproc
    """
    def __init__(self, status_str):
        """ Initializes things
            :param status_str: status string to print on error
        """
        self._status_str = status_str

    def Print(self, level, *msg):
        """ Prints debug message using the dsproc format
            :param level: debug level to issue at
            :param msg:   variable arguments (as expected by dsproc) to pass through
        """
        if   level is 0:
            dsproc.debug_lv0(*msg)
        elif level is 1:
            dsproc.debug_lv1(*msg)
        elif level is 2:
            dsproc.debug_lv2(*msg)
        elif level is 3:
            dsproc.debug_lv3(*msg)
        elif level is 4:
            dsproc.debug_lv4(*msg)
        elif level is 5:
            dsproc.debug_lv5(*msg)

    def Warning(self, *msg):
        """ Prints a warning message using dsproc format
            :param msg: variable arguments (As expected by dsproc) to pass through
        """
        dsproc.warning(*msg)

    def Error(self, *msg):
        """ Prints error message using dsproc format
            :param msg: variable arguments (As expected by dsproc) to pass through
        """
        dsproc.error(self._status_str, *msg)

    def PrintWarning(self, level, *msg):
        """ Prints both debug level and warning using dsroc format
            :param msg: variable arguments (As expected by dsproc) to pass through
        """
        self.Print(level, *msg)
        self.Warning(*msg)

    def PrintError(self, level, *msg):
        """ Prints both debug level and warning using dsroc format
            :param msg: variable arguments (As expected by dsproc) to pass through
        """
        self.Print(level, *msg)
        self.Error(*msg)


def GetValueOrMissingIfNone(val):
    """ Quick check if value is set to None, and if so returns MISSING_VALUE, so we can store it in a dataset
        without much problems.

        :param val: value to test
        :return: either value or MISSING_VALUE if None
    """
    if val is None:
        return MISSING_VALUE
    else:
        return val


def GetDatetimeFromGmTime(in_time_as_float):
    """ Helper to convert from GM time float that DMF stores into datetime, which is much easier to compute on
        Note: we drop microseconds since they are not of much consequence anyway

        :param in_time_as_float: input GM time as float
        :return: datetime version of the time
    """
    time_raw = time.gmtime(in_time_as_float)
    return datetime.datetime(year   = time_raw.tm_year,
                             month  = time_raw.tm_mon,
                             day    = time_raw.tm_mday,
                             hour   = time_raw.tm_hour,
                             minute = time_raw.tm_min,
                             second = time_raw.tm_sec)


def GetGmTimeFromDatetime(in_time_as_datetime):
    """ Helper to convert from datetime into GM time float that DMF stores

        :param in_time_as_datetime: timestamp as datetime
        :return: float in GM time format corresponding to input
    """
    return calendar.timegm(in_time_as_datetime.timetuple())




# Initialize the process.
#  This function is used to do any up front process initialization that
#  is specific to this process, and to create the UserData structure that
#  will be passed to all hook functions.
#  If an error occurs in this function it will be appended to the log and
#  error mail messages, and the process status will be set appropriately.
#  @return
#    - void pointer to the UserData structure
#    - NULL if an error occurred

def init_process():
    sp = StatusPrinter('init_process fatal error')
    sp.Print(1, 'Creating user defined data structure\n')

    mydata          = UserData(dsproc.get_name())
    mydata.vapname  = dsproc.get_name()
    mydata.site     = dsproc.get_site()
    mydata.facility = dsproc.get_facility()

    # Get IDs of input netcdf datastream
    dsid_in = dsproc.get_input_datastream_id(MASC_A1_B1_DS_NAME, 'b1')
    if dsid_in < 0:
        return 0
    mydata.dsid_in = dsid_in

    # Get IDs of output datastreams
    dsid_outP = dsproc.get_output_datastream_id(MASC_C1_DS_NAME_PARTICLES, MASC_C1_DS_LEVEL)
    if dsid_outP < 0:
        return 0
    mydata.dsid_out_particles = dsid_outP

    dsid_outTB = dsproc.get_output_datastream_id(MASC_C1_DS_NAME_TIME_BINS, MASC_C1_DS_LEVEL)
    if dsid_outTB < 0:
        return 0
    mydata.dsid_out_time_bins = dsid_outTB

    # Get path to masc images
    img_dir = (os.getenv('DATASTREAM_DATA') + '/' + mydata.site + '/' + mydata.site +
                   'masc' +  mydata.facility + '.a1')
    mydata.img_dir = img_dir

    # Get path to configuration file
    config_json = MASC_CONFIG_FILE
    if not os.path.exists(config_json) or \
       not os.path.isfile(config_json):
        sp.PrintError(1, 'ERROR: cannot find JSON configuration file in %s', config_json)
        return 0
    mydata.config_json = config_json

    sp.Print(1, 'Success creating user defined data structure\n')
    return mydata



#  Finish the process.
#  This function frees all memory used by the UserData structure.
#  @param user_data  - void pointer to the UserData structure
def finish_process(user_data):
    dsproc.debug_lv1("Cleaning up user defined data structure for process\n")



#  Hook function called just after data retrieval.
#  This function will be called once per processing interval just after data
#  retrieval, but before the retrieved observations are merged and QC applied.
#  @param  user_data - void pointer to the UserData structure
#                      returned by the init_process() function
#  @param begin_date - the begin time of the current processing interval
#  @param end_date   - the end time of the current processing interval
#  @param ret_data - pointer to the parent CDSGroup containing all the
#  @return
#    -  1 if processing should continue normally
#    -  0 if processing should skip the current processing interval
#         and continue on to the next one.
#    - -1 if a fatal error occurred and the process should exit.

def post_retrieval_hook(user_data, begin_date, end_date, ret_data):
    sp = StatusPrinter('Error in post_retrieval_hook')

    # Loop over all observations
    obs_index = 0
    while obs_index >= 0:

        # Get the retrieved dataset, if no more obs then done.
        in_dsid = dsproc.get_input_datastream_id(MASC_A1_B1_DS_NAME, 'b1')
        if in_dsid < 0:
            return 0
        ret_ds = dsproc.get_retrieved_dataset(in_dsid, obs_index)
        if ret_ds is None:
            sp.Print(1, 'Finished looping over masc.b1, nobs = %d', obs_index)
            break  # all observations counted

        if dsproc.get_debug_level() > 1:
            name = "masc_post_retrieval_begin" + str(obs_index) + '.debug'
            dsproc.dump_retrieved_datasets("./debug_dumps", name, obs_index)

        # Get dimension lengths of time and camera
        n_samples = dsproc.get_dim_length(ret_ds, "time")
        if n_samples == 0:
            sp.PrintError(1, 'num samples dimension could not be fetched')
            return 0
        n_cams = dsproc.get_dim_length(ret_ds, "camera")
        if n_cams == 0:
            sp.PrintError(1, 'camera dimension could not be fetched')
            return 0

        # Create a new *_var in the retriever data structure by cloning an existing var in masc.b1 dimensioned by
        # (time, camera).  The only var like that is camera id. Get the camera_id var
        camera_id_var = dsproc.get_retrieved_var('camera_id', obs_index)
        if camera_id_var is None:
            sp.PrintError(1, 'Error retrieving camera_id var at observation index %d', obs_index)
            return -1


        def HelperVarCopier(var_info):
            """ Helper function to copy per-camera data, create new variable that's per-time and per-camera,
                then copy the per-camera data over

                :param var_info: dictionary with variable info to copy
            """
            # Get var we want to convert to time varying
            var_org = dsproc.get_retrieved_var(var_info['from'], obs_index)
            if var_org is None:
                sp.PrintError(1, 'Error retrieving per-camera var %s at observation index %d', var_info['from'], obs_index)
                return -1

            var_data = dsproc.get_var_data_index(var_org)
            if var_data is None:
                sp.PrintError(1, 'Error retrieving per-camera var data %s at observation index %d', var_info['from'], obs_index)
                return 0

            # Create new * by cloning camera id var.
            # Set args to create in same dataset, change data type to float/int, use same dimension names, and do
            # not copy data. By creating it in same dataset it will be associated with correct observation.
            var_new = dsproc.clone_var(camera_id_var, None, 'tmp_new', var_info['type'], None, 0)
            if var_new is None:
                sp.PrintError(1, 'Error cloning camera_id into var %s at observation index %d', var_info['from'], obs_index)
                return -1

            # Fix long_name and units attribute values
            for attr in ['units', 'long_name']:
                tmp_att = dsproc.get_att_text(var_org, attr)
                if tmp_att is None:
                    sp.PrintError(1,
                                  'Error: could not get attribute %s for var %s at observation index %d',
                                  attr,
                                  var_info['from'],
                                  obs_index)
                    return -1

                status = dsproc.set_att_text(var_new, attr, tmp_att)
                if status == 0:
                    sp.PrintError(1,
                                  'Error: could not set attribute %s for var copy %s at observation index %d',
                                  attr,
                                  var_info['from'],
                                  obs_index)
                    return -1
            ### end loop over attr ###

            # Set data values of new variable
            var_new_data = dsproc.alloc_var_data_index(var_new, 0, n_samples)
            if var_new_data is None:
                sp.PrintError(1, 'Error: could not allocate data for new var %s at observation index %d', var_info['from'], obs_index)
                return 0

            for j in range(n_samples):
                for i in range(n_cams):
                    var_new_data[j][i] = var_data[i]

            # Delete the existing fov variable.
            status = dsproc.delete_var(var_org)
            if status == 0:
                sp.PrintError(1, 'Error: could not delete old var %s at observation index %d', var_info['from'], obs_index)
                return -1

            # Rename the new variable, to match var deleted.
            status = var_new.rename(var_info['from'])
            if status == 0:
                sp.PrintError(1, 'Error: could not rename new var %s at observation index %d', var_info['from'], obs_index)
                return -1
        ### end HelperVarCopier() function ###

        # Variables we'd like to merge together from different observations. These are per-camera
        # and the result will be [per-time][per-camera]
        vars_to_merge = [
            {   'from': 'field_of_view',    'type': cds.FLOAT,  },
            {   'from': 'crop_from_bottom', 'type': cds.INT,    },
            {   'from': 'crop_from_top',    'type': cds.INT,    },
            {   'from': 'crop_from_left',   'type': cds.INT,    },
            {   'from': 'crop_from_right',  'type': cds.INT,    },
        ]

        # Do the conversion and copying
        for var_info in vars_to_merge:
            HelperVarCopier(var_info)

        if dsproc.get_debug_level() > 1:
            name = "masc_post_retrieval_end" + str(obs_index) + '.debug'
            dsproc.dump_retrieved_datasets("./debug_dumps", name, obs_index)

        obs_index += 1
    ### end while obs_index >= 0 ###

    return 1


#  Main data processing function.
#  This function will be called once per processing interval just after the
#  output datasets are created, but before they are stored to disk.

#  @param  user_data - void pointer to the UserData structure
#                      returned by the init_process() function
#  @param  begin_date - begin time of the processing interval
#  @param  end_date   - end time of the processing interval
#  @param  ret_data - retriever data merged
#  @return
#    -  1 if processing should continue normally
#    -  0 if processing should skip the current processing interval
#         and continue on to the next one.
#    - -1 if a fatal error occurred and the process should exit.

def process_data(proc_data, begin_date, end_date, input_data):
    mydata = proc_data
    sp     = StatusPrinter('process_data fatal error')

    # -------------------------------------------------------------
    # Get Retrieved Variable Data
    # -------------------------------------------------------------
    sp.Print(1, 'Getting retrieved data from input datastream')

    # Define variables parameterized by camera only (num_cams).
    # However, these were updated by post-retrieval hook to be (time, num_cams)
    invar_camera_names = [
        #               variable name           has qc flag
        InDataVarGetter('field_of_view',        False),
        InDataVarGetter('crop_from_top',        False),
        InDataVarGetter('crop_from_bottom',     False),
        InDataVarGetter('crop_from_left',       False),
        InDataVarGetter('crop_from_right',      False),
    ]

    def GetInputDataDict(var_names, input_ds_ptr):
        """ Helper function to retrieve data from input datastream. Returns None on error and signals
            an error message to debug layer

            :param var_names:    array of variables to fetch of type InDataVarGetter()
            :param input_ds_ptr: pointer to input dataset to look variables in (when get_retrieved_var fails)
            :return: dictionary of parameter pointers. 'param name' -> DataVarPtrs(). None on error
        """
        out_dict = {}
        for key in var_names:
            # try to get the variable
            name    = key.var_name
            ret_var = dsproc.get_retrieved_var(name, 0)
            if ret_var is None:
                # try to get it as a simple variable
                ret_var = dsproc.get_var(input_ds_ptr, name)
                if ret_var is None:
                    sp.PrintError(1, 'Error retrieving variable %s', name)
                    return None

            id_var = dsproc.get_var_data_index(ret_var)
            if id_var is None:
                sp.PrintError(1, 'Error getting index for variable %s', name)
                return None

            # try to get QC variable as well, if there is one
            qc_id_var = None
            if key.has_qc_var:
                qc_ret_var = dsproc.get_qc_var(ret_var)
                if qc_ret_var is None:
                    sp.PrintError(1, 'Error retrieving qc variable for %s', name)
                    return None

                qc_id_var = dsproc.get_var_data_index(qc_ret_var)
                if qc_id_var is None:
                    sp.PrintError(1, 'Error getting index for qc variable for %s', name)
                    return None

            # create object to return
            ptr_obj        = DataVarPtrs(id_var, qc_id_var)
            out_dict[name] = ptr_obj

        # return
        return out_dict
    ### end GetInputDataDict() function ###


    # -------------------------------------------------------------
    # Get samples times 
    # -------------------------------------------------------------
    sp.Print(1, 'Retrieving data from input')

    # Get the input dataset
    input_ds = dsproc.get_retrieved_dataset(mydata.dsid_in, 0)
    if input_ds is None:
        sp.PrintError(1, 'Error retrieving input dataset')
        return 0

    # can get time data from input dataset
    sample_times = dsproc.get_sample_times(input_ds, 0)
    if sample_times is None:
        sp.PrintError(1, 'Error retrieving number of time datapoints')
        return -1
    nsamples = len(sample_times)

    # get the number of cameras we're working with
    num_cams = dsproc.get_dim_length(input_ds, "camera")
    if num_cams == 0:
        sp.PrintError(1, 'Error retrieving input camera dimension')
        return 0
    sp.Print(1, 'Loaded %d number of cameras', num_cams)

    time_range = dsproc.get_time_range(input_ds)
    if time_range is None:
        sp.PrintError(1, 'Error retrieving time range for input dataset')
        return 0

    # get per-camera configuration data we transformed to include time dimension in post-retrieval hook
    invar_camera_data = GetInputDataDict(invar_camera_names, input_ds)
    if invar_camera_data is None:
        sp.PrintError(1, 'Error retrieving camera property variables from input data stream')
        return -1


    # -------------------------------------------------------------
    # Iniitialize new Variables
    # -------------------------------------------------------------
    sp.Print(1, 'Initializing output variables')

    # The variables have been created by ADI libraries
    # so we can grab them from output data structure

    # Get output datastream
    particle_output_ds = dsproc.get_output_dataset(mydata.dsid_out_particles, 0)
    if particle_output_ds is None:
        sp.PrintError(1, 'Error retrieving output particles dataset')
        return 0

    # Double check that ROI parameters (x,y) have dimension set properly 
    roi_dim = dsproc.get_dim_length(particle_output_ds, 'num_elems_roi_position')
    if not roi_dim == 2:
        sp.PrintError(1, 'Error retrieving num_elems_roi_position (%d). Must be 2', roi_dim)
        return 0

    # Double check number of cameras matches between input and output datastreams
    num_cams_out = dsproc.get_dim_length(particle_output_ds, 'camera')
    if num_cams_out < num_cams:
        sp.PrintError(1, 'Error, camera dimension mismatch. input (%d) must be <= output (%d)', num_cams, num_cams_out)
        return 0


    timebins_output_ds = dsproc.get_output_dataset(mydata.dsid_out_time_bins, 0)
    if particle_output_ds is None:
        sp.PrintError(1, 'Error retrieving output time bins dataset')
        return 0

    timebins_output_time_var = dsproc.get_time_var(timebins_output_ds)
    if timebins_output_time_var is None:
        sp.PrintError(1, 'Error retrieving time variable for time bins dataset')
        return 0


    # Create a dictionary to hold all of our data, for less verbose way to get pointers
    # to this data from our datastream
    particle_data_names = [
        #                variable name                                 has_qc_var      is_aggregate     dim_size2
        #                                                                      can_eq_missing dim_size1
        OutDataVarHelper('snowflake_id',                               False,  False,  False, 0,        0),
        OutDataVarHelper('snowflake_fall_speed',                       True,   False,  False, 0,        0),
        OutDataVarHelper('camera_id',                                  False,  False,  False, num_cams, 0),
        OutDataVarHelper('maximum_dimension',                          True,   True,   False, num_cams, 0),
        OutDataVarHelper('particle_area',                              True,   True,   False, num_cams, 0),
        OutDataVarHelper('particle_edge_touch',                        True,   True,   False, num_cams, 0),
        OutDataVarHelper('area_eq_radius',                             True,   True,   False, num_cams, 0),
        OutDataVarHelper('perimeter',                                  True,   True,   False, num_cams, 0),
        OutDataVarHelper('orientation',                                True,   True,   False, num_cams, 0),
        OutDataVarHelper('aspect_ratio',                               True,   True,   False, num_cams, 0),
        OutDataVarHelper('complexity',                                 True,   True,   False, num_cams, 0),
        OutDataVarHelper('geometric_cross_section',                    True,   True,   False, num_cams, 0),
        OutDataVarHelper('mean_pixel_intensity',                       True,   True,   False, num_cams, 0),
        OutDataVarHelper('mean_pixel_intensity_variability',           True,   True,   False, num_cams, 0),
        OutDataVarHelper('roi_focus',                                  True,   True,   False, num_cams, 0),
        OutDataVarHelper('num_objects',                                True,   True,   False, num_cams, 0),
        OutDataVarHelper('roi_position',                               True,   True,   False, num_cams, roi_dim),
        OutDataVarHelper('roi_bot_position',                           True,   True,   False, num_cams, 0),
        OutDataVarHelper('roi_half_width_height',                      True,   True,   False, num_cams, roi_dim),
        OutDataVarHelper('num_imgs_used_avg',                          True,   True,   True,  0,        0),
        OutDataVarHelper('maximum_dimension_avg',                      True,   True,   True,  0,        0),
        OutDataVarHelper('particle_area_avg',                          True,   True,   True,  0,        0),
        OutDataVarHelper('area_eq_radius_avg',                         True,   True,   True,  0,        0),
        OutDataVarHelper('perimeter_avg',                              True,   True,   True,  0,        0),
        OutDataVarHelper('orientation_avg',                            True,   True,   True,  0,        0),
        OutDataVarHelper('aspect_ratio_avg',                           True,   True,   True,  0,        0),
        OutDataVarHelper('complexity_avg',                             True,   True,   True,  0,        0),
        OutDataVarHelper('geometric_cross_section_avg',                True,   True,   True,  0,        0),
        OutDataVarHelper('mean_pixel_intensity_avg',                   True,   True,   True,  0,        0),
        OutDataVarHelper('mean_pixel_intensity_variability_avg',       True,   True,   True,  0,        0),
        OutDataVarHelper('flatness',                                   True,   True,   True,  0,        0),
    ]

    # List of elements we don't need to allocate

    # Create a dictionary to hold all of our data, for less verbose way to get pointers
    # to this data from our datastream.
    # NOTE: we use is_aggregate here to differentiate between time bin properties like num_particles_for_avg
    #       and averaged values like fall_speed_avg. This is important for setting QC bits and assigning MISSING_VALUE
    timebins_data_names = [
        #                variable name                                 has_qc_var      is_aggregate     dim_size2
        #                                                                      can_eq_missing dim_size1
        OutDataVarHelper('time_bounds',                                False,  False,  False, 0,        0),
        OutDataVarHelper('num_particles_total',                        True,   True,   False, 0,        0),
        OutDataVarHelper('num_particles_for_avg',                      True,   True,   False, 0,        0),
        OutDataVarHelper('fall_speed_avg',                             True,   True,    True, 0,        0),
        OutDataVarHelper('maximum_dimension_avg',                      True,   True,    True, 0,        0),
        OutDataVarHelper('particle_area_avg',                          True,   True,    True, 0,        0),
        OutDataVarHelper('area_eq_radius_avg',                         True,   True,    True, 0,        0),
        OutDataVarHelper('perimeter_avg',                              True,   True,    True, 0,        0),
        OutDataVarHelper('orientation_avg',                            True,   True,    True, 0,        0),
        OutDataVarHelper('aspect_ratio_avg',                           True,   True,    True, 0,        0),
        OutDataVarHelper('complexity_avg',                             True,   True,    True, 0,        0),
        OutDataVarHelper('geometric_cross_section_avg',                True,   True,    True, 0,        0),
        OutDataVarHelper('mean_pixel_intensity_avg',                   True,   True,    True, 0,        0),
        OutDataVarHelper('mean_pixel_intensity_variability_avg',       True,   True,    True, 0,        0),
        OutDataVarHelper('flatness_avg',                               True,   True,    True, 0,        0),
    ]


    def GetOutputDataDict(var_names, data_stream, data_stream_str):
        """ Helper function to retrieve data pointers to a given output datastream. Returns None on error and signals
            an error message to debug layer

            :param var_names:       array of variables to fetch of type InDataVarGetter()
            :param data_stream:     datastream object used to retrieve variables
            :param data_stream_str: string name for datastream, used for error output
            :return: None on error (status string was already printed)
                     Otherwise array: 0: map 'param name' -> index within var_names
                                      1: map 'param name' -> DataVarPtrs()
        """
        ret_names_dict     = {}
        ret_out_names_dict = {}
        data_var_index     = 0
        for data_var_helper in var_names:
            # data_var_helper is of type OutDataVarHelper()
            data_name    = data_var_helper.var_name
            tmp_data_ptr = dsproc.get_output_var(data_stream, data_name, 0)
            if tmp_data_ptr is None:
                sp.PrintError(1, 'Error retrieving output variable %s in %s datastream', data_name, data_stream_str)
                return None

            tmp_qc_data_ptr = None
            if data_var_helper.has_qc_var:
                qc_data_name    = 'qc_{0}'.format(data_name)
                tmp_qc_data_ptr = dsproc.get_output_var(data_stream, qc_data_name, 0)
                if tmp_qc_data_ptr is None:
                    sp.PrintError(1, 'Error retrieving output variable %s in %s datastream', qc_data_name, data_stream_str)
                    return None

            ret_names_dict    [data_name] = data_var_index
            ret_out_names_dict[data_name] = DataVarPtrs(tmp_data_ptr, tmp_qc_data_ptr)
            data_var_index += 1
        return [ret_names_dict, ret_out_names_dict]
    ### end GetOutputDataDict() function ###

    def AllocateOutputData(out_names_dict, data_stream_str, num_vals_to_alloc):
        """ Helper function to allocate space for given data pointers. Returns None on error and signals
            an error message to debug layer

            :param out_names_dict:    map 'param name' -> DataVarPtrs(). Typically called *_out_names_dict
            :param data_stream_str:   string name for datastream, used for error output
            :param num_vals_to_alloc: total number of values to allocate
            :return: None on error (status string was already printed)
                     Otherwise, 'param name' -> DataVarPtrs()
        """
        ret_data_dict = {}
        for data_key in out_names_dict:
            # Not sure if we should skip allocation. Things seem to work without, so will keep this for simplicity
            # Otherwise, for mascparticles, we need to skip the following variables (copied from source):
            #     snowflake_id, snowflake_fall_speed, qc_snowflake_fall_speed, camera_id
            # Note that qc_camera_id has to be allocated.
            # check this is a key we don't need to allocate memory for.
            #if dataKey is "snowflake_id"            or \
            #    continue
            data_value = out_names_dict[data_key]

            # get variable
            tmp_data_ptr = dsproc.alloc_var_data_index(data_value.var_ptr, 0, num_vals_to_alloc)
            if tmp_data_ptr is None:
                sp.PrintError(1, 'Error allocating id for output variable %s in %s datastream', data_key, data_stream_str)
                return None

            # get QC variable
            tmp_qc_data_ptr = None
            if data_value.qc_var_ptr is not None:
                tmp_qc_data_ptr = dsproc.alloc_var_data_index(data_value.qc_var_ptr, 0, num_vals_to_alloc)
                if tmp_qc_data_ptr is None:
                    sp.PrintError(1, 'Error allocating id for output variable qc_%s in %s datastream', data_key, data_stream_str)
                    return None

            ret_data_dict[data_key] = DataVarPtrs(tmp_data_ptr, tmp_qc_data_ptr)
        return ret_data_dict
    ### end AllocateOutputData() function ###

    def GetVarAttribute(var_dict, var_name, attr_name, attr_type):
        """ Helper function which gets variable attributes like valid_min. If returns None, then there's an error.
            Error message is displayed

            :param var_dict:  dictionary 'var name' -> DataVarPtrs(). Typically called *_out_names_dict
            :param var_name:  name of the variable to look up the bound for
            :param attr_name: name of the attribute to look up
            :param attr_type: type of the attribute, eg: cds.INT, ent
            :return: variable attribute or None on error
        """
        var_to_get = var_dict[var_name].var_ptr
        var_bound  = dsproc.get_att_value(var_to_get, attr_name, attr_type)
        if var_bound is None:
            sp.PrintError(1, 'Error retrieving %s from %s variable', attr_name, var_name)
        return var_bound
    ### end GetVarAttribute() function ###


    # Now get data pointers. Typical pattern for this would be:
    # p_snowflake_fall_speed_var = dsproc.get_output_var(mydata.dsid_out_particles,
    #                        "snowflake_fall_speed", 0)
    # if p_snowflake_fall_speed_var is None:
    #     return -1

    # particles output
    parse_vars_particles = GetOutputDataDict(var_names       = particle_data_names,
                                             data_stream     = mydata.dsid_out_particles,
                                             data_stream_str = MASC_C1_DS_NAME_PARTICLES)
    if parse_vars_particles is None:
        return -1
    particle_data_names_dict     = parse_vars_particles[0]  # map: data name -> array index within particle_data_names[]
    particle_data_out_names_dict = parse_vars_particles[1]  # map: data name -> DataVarPtrs()

    # time bins output
    parse_vars_timebins = GetOutputDataDict(var_names       = timebins_data_names,
                                            data_stream     = mydata.dsid_out_time_bins,
                                            data_stream_str = MASC_C1_DS_NAME_TIME_BINS)
    if parse_vars_timebins is None:
        return -1
    timebins_data_names_dict     = parse_vars_timebins[0]   # map: data name -> array index within particle_data_names[]
    timebins_data_out_names_dict = parse_vars_timebins[1]   # map: data name -> DataVarPtrs()


    # Before allocation, get necessary variable bounds
    sp.Print(1, 'Gathering variable bounds')

    # fallspeed has an additional limit here, used for binning particles in time
    warn_max_fall_speed = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                          var_name  = 'snowflake_fall_speed',
                                          attr_name = 'warn_max',
                                          attr_type = cds.FLOAT)
    if warn_max_fall_speed is None:
        return -1

    warn_min_cross_section = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                             var_name  = 'geometric_cross_section',
                                             attr_name = 'warn_min',
                                             attr_type = cds.FLOAT)
    if warn_min_cross_section is None:
        return -1

    warn_max_particle_edge_touch = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                                   var_name  = 'particle_edge_touch',
                                                   attr_name = 'warn_max',
                                                   attr_type = cds.FLOAT)
    if warn_max_particle_edge_touch is None:
        return -1

    warn_min_mean_pixel_intensity = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                                    var_name  = 'mean_pixel_intensity',
                                                    attr_name = 'warn_min',
                                                    attr_type = cds.FLOAT)
    if warn_min_mean_pixel_intensity is None:
        return -1

    warn_min_mean_pixel_intensity_variability = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                                                var_name  = 'mean_pixel_intensity_variability',
                                                                attr_name = 'warn_min',
                                                                attr_type = cds.FLOAT)
    if warn_min_mean_pixel_intensity_variability is None:
        return -1

    warn_min_roi_focus = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                         var_name  = 'roi_focus',
                                         attr_name = 'warn_min',
                                         attr_type = cds.FLOAT)
    if warn_min_roi_focus is None:
        return -1

    warn_min_roi_bot_position = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                                var_name  = 'roi_bot_position',
                                                attr_name = 'warn_min',
                                                attr_type = cds.FLOAT)
    if warn_min_roi_bot_position is None:
        return -1

    warn_max_roi_bot_position = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                                var_name  = 'roi_bot_position',
                                                attr_name = 'warn_max',
                                                attr_type = cds.FLOAT)
    if warn_max_roi_bot_position is None:
        return -1

    valid_min_num_imgs_used_avg = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                                  var_name  = 'num_imgs_used_avg',
                                                  attr_name = 'valid_min',
                                                  attr_type = cds.INT)
    if valid_min_num_imgs_used_avg is None:
        return -1

    warn_min_num_imgs_used_avg = GetVarAttribute(var_dict  = particle_data_out_names_dict,
                                                 var_name  = 'num_imgs_used_avg',
                                                 attr_name = 'warn_min',
                                                 attr_type = cds.INT)
    if warn_min_num_imgs_used_avg is None:
        return -1


    warn_min_num_particles_for_avg = GetVarAttribute(var_dict  = timebins_data_out_names_dict,
                                                     var_name  = 'num_particles_for_avg',
                                                     attr_name = 'warn_min',
                                                     attr_type = cds.INT)
    if warn_min_num_particles_for_avg is None:
        return -1

    # Figure out if our time bin widths are good. We assume that min/max bounds are [1, 3600]
    valid_time_bin_offsets = GetVarAttribute(var_dict  = timebins_data_out_names_dict,
                                             var_name  = 'time_bounds',
                                             attr_name = 'bound_offsets',
                                             attr_type = cds.DOUBLE)
    if valid_time_bin_offsets is None:
        return -1

    # Now check time bin width parameter
    bin_width           = valid_time_bin_offsets[1] - valid_time_bin_offsets[0]
    valid_min_bin_width = 1
    valid_max_bin_width = 3600
    qc_bin_width_less_than_min       = bin_width < valid_min_bin_width
    qc_bin_width_greater_than_max    = bin_width > valid_max_bin_width
    qc_bin_width_doesnot_divide_hour = 3600 % bin_width
    skip_time_binning = (qc_bin_width_less_than_min or
                         qc_bin_width_greater_than_max or
                         qc_bin_width_doesnot_divide_hour)

    # Figure out the left bound of the very first time bin
    # Note, care must be taken to work between time.gmtime(), datetime and calendar.timegm(datetime.timetuple())
    # to make sure times are set correctly
    if skip_time_binning:
        sp.Print(1, 'Something happened, so time binning will not be computed')
        sp.Print(1,
                 '  bin_width: %f given by bound_offsets (%f, %f), valid range [%f, %f], divides 3600? %d',
                 bin_width,
                 valid_time_bin_offsets[0],
                 valid_time_bin_offsets[1],
                 valid_min_bin_width,
                 valid_max_bin_width,
                 not qc_bin_width_doesnot_divide_hour)


    # Allocate the data arrays. Typical pattern for this would be:
    # maximum_dimension = dsproc.alloc_var_data_index(
    #                maximum_dimension_var, 0, nsamples)
    # if maximum_dimension is None:
    #     return -1
    sp.Print(1, 'Allocating memory for output variables')

    # particles output
    particle_data_out_dict = AllocateOutputData(out_names_dict    = particle_data_out_names_dict,
                                                data_stream_str   = MASC_C1_DS_NAME_PARTICLES,
                                                num_vals_to_alloc = nsamples)
    if particle_data_out_dict is None:
        return -1


    # -------------------------------------------------------------
    # Begin analysis
    # -------------------------------------------------------------

    def ClearAllParticleOutputVars(index,
                                   set_per_camera,
                                   set_avg,
                                   camera_id,
                                   qc_fall_speed_is_bad,
                                   qc_cur_camera_id_was_missing,
                                   qc_cur_camera_img_was_missing,
                                   qc_cur_img_has_no_particle,
                                   qc_all_camera_ids_were_missing,
                                   qc_num_imgs_used_avg_was_missing,
                                   qc_num_imgs_used_avg_less_valid_min,
                                   qc_num_imgs_used_avg_less_warn_min):
        """ Sets per-particle datastream (mascparticles.c1) output data (only non-QC variables) to MISSING_VALUE.
            Common bits between QC variable types are set according to input parameters. Combination of flags:
                flagSetPerCamera    camera          outcome
                False               <any>           per-camera data left alone
                True                None            all per-camera data is set to MISSING_VALUE
                True                [0, num_cams]   only values at camera index set to MISSING_VALUE

            QC bits set for each per-camera variable (order may change):
                qc_fall_speed_was_missing
                qc_cur_camera_id_was_missing
                qc_cur_camera_img_was_missing
                qc_cur_img_has_no_particle

            QC bits set for all averaged variables (order may change):
                qc_fall_speed_was_missing
                qc_all_camera_ids_were_missing
                qc_num_imgs_used_avg_was_missing
                qc_num_imgs_used_avg_less_valid_min
                qc_num_imgs_used_avg_less_warn_min

            :param index:           index within array to set, corresponds to time dimension
            :param set_per_camera:  flag whether to set per-camera variables to MISSING_VALUE
            :param set_avg:         flag whether to set average (derived) variables to MISSING_VALUE
            :param camera_id:       camera index of data to set applies only when per-camera is activated
            :param qc_fall_speed_is_bad:                when input qc_snowflake_fall_speed > 0
            :param qc_cur_camera_id_was_missing:        when input camera_id == MISSING_VALUE
            :param qc_cur_camera_img_was_missing:       when camera image can't be opened
            :param qc_cur_img_has_no_particle:          when no particles were detected in current image
            :param qc_all_camera_ids_were_missing:      when every input camera_id == MISSING_VALUE
            :param qc_num_imgs_used_avg_was_missing:    when num_imgs_used_avg == MISSING_VALUE for this particle
            :param qc_num_imgs_used_avg_less_valid_min: when num_imgs_used_avg < valid_min for this particle
            :param qc_num_imgs_used_avg_less_warn_min:  when num_imgs_used_avg < warn_min for this particle
        """
        # aggregate bits together
        agg_bits_per_camera = 0
        agg_bits_avg        = 0

        if qc_fall_speed_is_bad:
            agg_bits_per_camera |= 0x1
            agg_bits_avg        |= 0x1

        if qc_cur_camera_id_was_missing:
            agg_bits_per_camera |= 0x2

        if qc_cur_camera_img_was_missing:
            agg_bits_per_camera |= 0x4

        if qc_cur_img_has_no_particle:
            agg_bits_per_camera |= 0x8

        if qc_all_camera_ids_were_missing:
            agg_bits_avg        |= 0x2

        if qc_num_imgs_used_avg_was_missing:
            agg_bits_avg        |= 0x4

        if qc_num_imgs_used_avg_less_valid_min:
            agg_bits_avg        |= 0x8

        if qc_num_imgs_used_avg_less_warn_min:
            agg_bits_avg        |= 0x10

        # set all particle data to MISSING_VALUE where appropriate
        for d_key in particle_data_out_dict:
            key_props_id = particle_data_names_dict[d_key]
            key_props    = particle_data_names     [key_props_id]

            # is this variable even settable?
            if not key_props.can_eq_missing:
                continue

            # gets pointer to array of data values and corresponding QC parameters
            d_var    = particle_data_out_dict[d_key].var_ptr
            d_qc_var = particle_data_out_dict[d_key].qc_var_ptr

            # set average
            # NOTE: assumed that aggregates are not arrays
            if set_avg and \
               key_props.is_aggregate:
                d_var[index] = MISSING_VALUE

                # attempt to set QC variable
                if d_qc_var is not None:
                    if not d_key == 'num_imgs_used_avg':
                        d_qc_var[index] = agg_bits_avg
                    else:
                        # qc_num_imgs_used_avg shares only 2 least bits with others
                        d_qc_var[index] = (agg_bits_avg & 0x3)

            # set per-camera value
            if set_per_camera and \
               key_props.dim_size1 > 0:

                # small helper to set per-camera data
                def PerCameraSetterHelper(cam_id):
                    # no 3rd dimension
                    if key_props.dim_size2 == 0:
                        d_var[index][cam_id] = MISSING_VALUE
                        if d_qc_var is not None:
                            d_qc_var[index][cam_id] = agg_bits_per_camera

                    # 3rd dimension (like ROI)
                    else:
                        for d in range(key_props.dim_size2):
                            d_var[index][cam_id][d] = MISSING_VALUE
                            if d_qc_var is not None:
                                d_qc_var[index][cam_id][d] = agg_bits_per_camera
                ### end PerCameraSetterHelper() ###

                # all?
                if camera_id is None:
                    for c in range(key_props.dim_size1):
                        PerCameraSetterHelper(c)

                # specific camera?
                else:
                    PerCameraSetterHelper(camera_id)
        ### end d_key for loop ###
    ### end ClearAllParticleOutputVars() function ###

    def ClearAllTimeBinOutputVars(index,
                                  set_bin_props,
                                  set_bin_avgs,
                                  qc_num_particles_avg_missing,
                                  qc_num_particles_avg_less_warn,
                                  qc_num_particles_avg_is0):
        """ Sets time bins datastream (masctimebins.c1) output data (only non-QC variables) to MISSING_VALUE.
            Common bits between QC variable types are set according to input parameters

            QC bits set for all averaged variables (order may change):
                qc_num_particles_avg_missing
                <bit not set when we are set to MISSING_VALUE>
                qc_num_particles_avg_is0

            :param index:           index within array to set, corresponds to time dimension
            :param set_bin_props:   flag whether to set time bin variables to MISSING_VALUE
            :param set_avg:         flag whether to set average (derived) variables to MISSING_VALUE
            :param qc_num_particles_avg_missing:    when num_particles_for_avg == MISSING_VALUE
            :param qc_num_particles_avg_less_warn:  when num_particles_for_avg <  warn_min
            :param qc_num_particles_avg_is0:        when num_particles_for_avg == 0
        """
        # aggregate bits together. We set bit 1 to true, since value is set to MISSING_VALUE
        agg_bits_avg = 0x1

        if qc_num_particles_avg_missing:
            agg_bits_avg |= 0x2

        if qc_num_particles_avg_less_warn:
            agg_bits_avg |= 0x4

        if qc_num_particles_avg_is0:
            agg_bits_avg |= 0x8

        # set all time bin data to MISSING_VALUE where appropriate
        for d_key in timebins_data_out_dict:
            key_props_id = timebins_data_names_dict[d_key]
            key_props    = timebins_data_names     [key_props_id]

            # is this variable even settable?
            if not key_props.can_eq_missing:
                continue

            # gets pointer to array of data values and corresponding QC parameters
            d_var    = timebins_data_out_dict[d_key].var_ptr
            d_qc_var = timebins_data_out_dict[d_key].qc_var_ptr

            # set averaged values
            if set_bin_avgs and \
               key_props.is_aggregate:
                d_var[index] = MISSING_VALUE

                # attempt to set QC variable
                if d_qc_var is not None:
                    d_qc_var[index] = agg_bits_avg

            # set time bin values
            if set_bin_props and \
               not key_props.is_aggregate:
                d_var[index] = MISSING_VALUE
    ### end ClearAllTimeBinOutputVars() function ###

    # profiling data run
    profile_num_imgs       = 0
    profile_num_particles  = 0
    profile_worst_time     = 0
    profile_worst_particle = 0
    profile_time_start     = timeit.default_timer()

    if flagEnableProfile:
        profiler = cProfile.Profile()

    # initialize and set some things up
    mydata.platform = mydata.site + MASC_A1_B1_DS_NAME + mydata.facility + '.a1'

    # Load image analysis with appropriate defaults here
    config_json_dict = None
    try:
        # load default JSON configuration parameters from configuration file
        config_json_dict = DataAnalysisConfig.LoadFromJSONFile(mydata.config_json)

        # update them to correspond to what is stored within datastream
        # NOTE: we have to be careful about converting from datastream units into correct units stored
        # image processing
        img_settings = config_json_dict['imageAnalysisParameters']
        img_settings['minFlakeSizeInMicrons']                 = float(math.sqrt(warn_min_cross_section[0]) * 1000.)
        img_settings['maxEdgeTouchLengthInMicrons']           = float(warn_max_particle_edge_touch[0] * 1000.)
        img_settings['minMaxPixelIntensity01']                = float(warn_min_mean_pixel_intensity[0])
        img_settings['rangeIntensityThreshold01']             = float(warn_min_mean_pixel_intensity_variability[0])
        img_settings['flagSaveCroppedImages']                 = False
        img_settings['focusThreshold01']                      = float(warn_min_roi_focus[0])
        img_settings['boundingBoxThresholdInMM']['bottomMin'] = float(warn_min_roi_bot_position[0])
        img_settings['boundingBoxThresholdInMM']['bottomMax'] = float(warn_max_roi_bot_position[0])

        # update per-camera parameters (checking the data is not None or negative)
        # NOTE: for now, let's just double check the number of cameras is correct
        cam_settings = img_settings['perCamera']
        if len(cam_settings) is not num_cams:
            sp.PrintError(1, 'ERROR: number of cameras in configuration file %d different from datastream %d', len(cam_settings), num_cams)
            return -1
        # NOTE: we no longer need to set per-camera parameters beyond the default because the 1st particle
        # that has different values for these will update our analysis parameters

        # time binning
        bin_settings = config_json_dict['timeBinningParameters']
        bin_settings['binWidthInSec']          = float(bin_width)
        bin_settings['maxFallSpeedInMetersPS'] = float(warn_max_fall_speed[0])
        bin_settings['minNumParticlesPerBin']  = float(warn_min_num_particles_for_avg[0])

        # set these (performs sanity check)
        image_analysis_params = ImageAnalyzer.Parameters()
        image_analysis_params.InitFromJSONDict(config_json_dict)
        particle_analyzer     = ParticleAnalyzer(image_analysis_params)
    except Exception as e:
        sp.PrintError(1, 'Error setting up image analyzer\n%s\nTrace:\n%s', e, traceback.format_exc())
        return -1

    # print out the parameters before processing just in case
    tmp_anl_dict = image_analysis_params.GetJSONDict()
    sp.Print(1, '=== Default Image Analyzer Parameters ===\n%s\n======', DataAnalysisConfig.GetJSONString([tmp_anl_dict], 3))


    # save parameters (without per-camera) as a string to global attribute for per-particle output dataset
    config_json_dict_cpy = copy.deepcopy(config_json_dict)
    del config_json_dict_cpy['imageAnalysisParameters']['perCamera']
    
    status = dsproc.set_att_text(particle_output_ds, 'anal_config_json', json.dumps(config_json_dict_cpy, indent = None))
    if status == 0:
        sp.PrintError(1, 'Error writing out anal_config_json attribute')
        return 0


    def UpdateConfigPerCameraInfo(new_per_cam_dict):
        """ Checks if new values are different from current configuration parameters. If so, overwrites them,
            initializes the analyzer and prints new values.

            :param new_per_cam_dict: per-camera dictionary with new parameters
            :return success of operation
        """
        try:
            needsUpdate = False
            curPerCam   = config_json_dict['imageAnalysisParameters']['perCamera']
            for c in range(num_cams):
                newCamFOV   = new_per_cam_dict[c]['horizFOVPerPixelInMM']
                newCrop     = new_per_cam_dict[c]['cropAtCapture']
                newCamCropT = newCrop['top']
                newCamCropB = newCrop['bottom']
                newCamCropL = newCrop['left']
                newCamCropR = newCrop['right']

                if newCamFOV > 0 and \
                   not curPerCam[c]['horizFOVPerPixelInMM'] == newCamFOV:
                    curPerCam[c]['horizFOVPerPixelInMM'] = newCamFOV
                    needsUpdate = True
                curCamCrop = curPerCam[c]['cropAtCapture']

                def CamCropHelper(name, newVal):
                    if newVal >= 0 and \
                       not curCamCrop[name] == newVal:
                        curCamCrop[name] = newVal
                        return True
                    return False
                ### end CamHelper() function ###

                needsUpdate |= CamCropHelper('top',    newCamCropT)
                needsUpdate |= CamCropHelper('bottom', newCamCropB)
                needsUpdate |= CamCropHelper('left',   newCamCropL)
                needsUpdate |= CamCropHelper('right',  newCamCropR)

            # actually update parameters if needed
            if needsUpdate:
                particle_analyzer.UpdateFromJSONDict(config_json_dict)

                # print out the parameters before processing just in case
                tmp_anl_dict = image_analysis_params.GetJSONDict()
                sp.Print(1, '=== Updated Image Analyzer Parameters ===\n%s\n======', DataAnalysisConfig.GetJSONString([tmp_anl_dict], 3))
            return True

        except Exception as e:
            sp.PrintError(1, 'Error setting up image analyzer\n%s\nTrace:\n%s', e, traceback.format_exc())
            return False
    ### end UpdateConfigPerCameraInfo() function ###


    def LoadPerCameraConfig(flake_id):
        """ Helper to create a per-camera dictionary we can use to update analysis configuration

            :param flake_id: particle id to look up
            :return: dictionary with per-camera data for this particle
        """
        array_to_ret = []
        for c in range(num_cams):
            dict_to_ret = {
                'horizFOVPerPixelInMM': invar_camera_data['field_of_view'].var_ptr[flake_id][c],
                'cropAtCapture': {
                    'top':      invar_camera_data['crop_from_top'   ].var_ptr[flake_id][c],
                    'bottom':   invar_camera_data['crop_from_bottom'].var_ptr[flake_id][c],
                    'left':     invar_camera_data['crop_from_left'  ].var_ptr[flake_id][c],
                    'right':    invar_camera_data['crop_from_right' ].var_ptr[flake_id][c],
                },
            }
            array_to_ret.append(dict_to_ret)
        return array_to_ret
    ### end LoadPerCameraConfig() function ###


    # Build up a collection of particles to be used to generate time-series
    all_particles                = []
    num_bad_complexity_particles = 0

    # loop over sample times
    for i in range(nsamples):
        # get some references
        fall_speed_ref    = particle_data_out_dict['snowflake_fall_speed'].var_ptr
        qc_fall_speed_ref = particle_data_out_dict['snowflake_fall_speed'].qc_var_ptr
        cur_flake_id      = particle_data_out_dict['snowflake_id'        ].var_ptr[i]
        cur_camera_id_ref = particle_data_out_dict['camera_id'           ].var_ptr[i]

        sp.Print(1, '=======> particle %d at index %d of %d ====', cur_flake_id, i, nsamples)

        # (potentially) update per-camera configuration parameters that came along with this particle?
        UpdateConfigPerCameraInfo(LoadPerCameraConfig(i))

        # even is a sample has a bad fall speed value, we'll process the rest anyway
        qc_fallspeed_bad_val = False
        if qc_fall_speed_ref[i] > 0:
            # depending on which bit was set, we have to set different parts of our datastream to MISSING_VALUE
            # bit_1: value is equal to missing_value
            qc_fallspeed_bad_val = True

        # fallspeed may be good, double check that this new fallspeed value is < valid_max
        # that was set within this datastream
        if fall_speed_ref[i] > warn_max_fall_speed[0]:
            qc_fall_speed_ref[i] |= 0x8

        # set all output variables to be 'missing'
        ClearAllParticleOutputVars(index          = i,
                                   set_per_camera = True,
                                   set_avg        = True,
                                   camera_id      = None,
                                   qc_fall_speed_is_bad                = qc_fallspeed_bad_val,
                                   qc_cur_camera_id_was_missing        = False,
                                   qc_cur_camera_img_was_missing       = False,
                                   qc_cur_img_has_no_particle          = False,
                                   qc_all_camera_ids_were_missing      = False,
                                   qc_num_imgs_used_avg_was_missing    = False,
                                   qc_num_imgs_used_avg_less_valid_min = False,
                                   qc_num_imgs_used_avg_less_warn_min  = False)

        # build up a particle for processing
        particle_time = time.gmtime(sample_times[i])
        particle_data = {
            EnumParserColumns.FLAKE_ID:   cur_flake_id,
            EnumParserColumns.DATE_STR:   time.strftime('%m.%d.%Y', particle_time),
            EnumParserColumns.TIME_STR:   time.strftime('%H:%M:%S.000000', particle_time),
            EnumParserColumns.FALL_SPEED: fall_speed_ref[i]
        }
        particle_to_process = FlakeInfo()
        particle_to_process.SetFallspeed(particle_data)

        # counts how many images we were able to find/open
        num_good = 0

        # flag to specify whether all images contained no or "bad" particles (they
        # miss quality thresholds). Used to set a quality bit for num_imgs_used_avg
        # Set to False once any image contains a "good" particle
        no_imgs_have_good_particles = True

        # loop over three camera ids and build image file names
        # we can actually tolerate missing images
        for j in range(num_cams):
            # per-camera QC parameters that affect analysis just for this camera
            qc_camera_image_missing = False

            # if camera id missing, then skip to next camera id
            cur_camera_id = cur_camera_id_ref[j]
            if cur_camera_id == MISSING_VALUE:
                sp.Print(1, '   particle %d, camera %d, cam_id_missing', cur_flake_id, j)
                ClearAllParticleOutputVars(index          = i,
                                           set_per_camera = True,
                                           set_avg        = False,
                                           camera_id      = j,
                                           qc_fall_speed_is_bad                = qc_fallspeed_bad_val,
                                           qc_cur_camera_id_was_missing        = True,
                                           qc_cur_camera_img_was_missing       = True,
                                           qc_cur_img_has_no_particle          = True,
                                           qc_all_camera_ids_were_missing      = False,
                                           qc_num_imgs_used_avg_was_missing    = False,
                                           qc_num_imgs_used_avg_less_valid_min = False,
                                           qc_num_imgs_used_avg_less_warn_min  = False)
                continue 

            # Snowflake file images follow this name convention:
            # olimascM1.a1.20151028.221934.png.id_00001726_cam_2.png
            # [platform].[date: YYYYMMDD.HHMMSS].png.id_[flake id]_cam_[camera id].png
            # However, particle capture time does not (typically) match image time stamps. So we'll generate a
            # few guesses to try and pick the first one that fits.
            capture_time   = GetDatetimeFromGmTime(sample_times[i])
            times_to_check = [capture_time + datetime.timedelta(seconds = x) for x in [-1, 0, 1]]
            file_strs      = []
            for t in times_to_check:
                date_str = t.strftime('%Y%m%d.%H%M%S')
                file_str = '{0}/{1}.{2}.png.id_{3:08d}_cam_{4}.png'.format(mydata.img_dir,
                                                                           mydata.platform,
                                                                           date_str,
                                                                           cur_flake_id,
                                                                           cur_camera_id)
                file_strs.append(file_str)

            # check a bunch of files, issue warning only when nothing matches
            file_found = False
            for file_name in file_strs:
                if os.path.isfile(file_name):
                    file_found = True
                    sp.Print(1, '   Opening file: %s', file_name)
                    try:
                        open(file_name, 'rb')
                        # save filename into particle info
                        image_to_add = {
                            EnumParserColumns.CAMERA_ID:      cur_camera_id,
                            #EnumParserColumns.DATE_STR:
                            #EnumParserColumns.TIME_STR:
                            EnumParserColumns.IMAGE_NAME_STR: file_name
                        }
                        particle_to_process.AddImage(image_to_add)
                        num_good += 1
                    except:
                        sp.PrintError(1, '   === Error opening file: %s', file_name)
                        qc_camera_image_missing = True
                    break
            if not file_found:
                sp.Print(1,
                         'File not found for date %s, flake id %d, camera %d',
                         capture_time.strftime('%Y-%m-%d %H:%M:%S'),
                         cur_flake_id,
                         cur_camera_id)
                qc_camera_image_missing = True

            # Set QC for missing camera image
            if qc_camera_image_missing:
                # if we can't find the file based on the given timestamp (of the snowflake, rather than the image)
                # then we issue an error and return -1
                sp.PrintError(1, '   === Error opening image file at time: %s tried filenames: %s',
                              capture_time.strftime('%Y-%m-%d %H:%M:%S'),
                              file_strs)
                return -1

                ClearAllParticleOutputVars(index          = i,
                                           set_per_camera = True,
                                           set_avg        = False,
                                           camera_id      = j,
                                           qc_fall_speed_is_bad                = qc_fallspeed_bad_val,
                                           qc_cur_camera_id_was_missing        = False,
                                           qc_cur_camera_img_was_missing       = True,
                                           qc_cur_img_has_no_particle          = True,
                                           qc_all_camera_ids_were_missing      = False,
                                           qc_num_imgs_used_avg_was_missing    = False,
                                           qc_num_imgs_used_avg_less_valid_min = False,
                                           qc_num_imgs_used_avg_less_warn_min  = False)
        ### end j for loop (num_cams) ###

        # Badness - we have 0 good images for this flake
        if num_good == 0:
            ClearAllParticleOutputVars(index          = i,
                                       set_per_camera = False,
                                       set_avg        = True,
                                       camera_id      = None,
                                       qc_fall_speed_is_bad                = qc_fallspeed_bad_val,
                                       qc_cur_camera_id_was_missing        = False,
                                       qc_cur_camera_img_was_missing       = False,
                                       qc_cur_img_has_no_particle          = False,
                                       qc_all_camera_ids_were_missing      = True,
                                       qc_num_imgs_used_avg_was_missing    = True,
                                       qc_num_imgs_used_avg_less_valid_min = False,
                                       qc_num_imgs_used_avg_less_warn_min  = False)
            continue

        # Process this flake. All results are stored within
        sp.Print(1, '   processing particle %d...', cur_flake_id)
        sp.Print(1, '   capture time: %f == %s', sample_times[i], '{0}'.format(particle_time))

        if flagEnableProfile:
            profiler.enable()
        profile_part_begin = timeit.default_timer()

        # Is there an error during processing?
        try:
            particle_analyzer.AnalyzeParticles([particle_to_process])
            sp.Print(1, '   filter results (true if passed):\n%s', particle_to_process.aggregatedAnalysisResults.quality.GetString("    "))

        except Exception as e:
            sp.PrintError(1, 'Error when analyzing particles\n%s\nTrace:\n%s', e, traceback.format_exc())
            return 0

        profile_part_time  = timeit.default_timer() - profile_part_begin
        if flagEnableProfile:
            profiler.disable()
            s     = StringIO.StringIO()
            pstat = pstats.Stats(profiler, stream = s).sort_stats('cumulative')
            pstat.print_stats()
            sp.Print(1, '   ----- Profiling output -----\n%s\n----------', s.getvalue())
        sp.Print(1, '   processing time (sec): %f', profile_part_time)

        # update profiling stats
        profile_num_particles += 1
        profile_num_imgs      += len(particle_to_process.imageData)
        if profile_worst_time < profile_part_time:
            profile_worst_time     = profile_part_time
            profile_worst_particle = 'time: {0}, particle id: {1}'.format(particle_to_process.captureDateTime.dateTime,
                                                                          particle_to_process.flakeId)


        # Extract analysis data from particle. First, per-camera data
        # Note: we only stored images that needed processing
        for img in particle_to_process.imageData:
            cur_camera_id = img.cameraId
            cur_img_anl   = img.analysisResults

            # In case we found no flakes at all (regardless of their goodness)
            # Also sets the num_objects to MISSING_VALUE and proper bit corresponding to
            # having no "good" particle detected
            if cur_img_anl            is None or \
               cur_img_anl.numObjects is None:
                ClearAllParticleOutputVars(index          = i,
                                           set_per_camera = True,
                                           set_avg        = False,
                                           camera_id      = cur_camera_id,
                                           qc_fall_speed_is_bad                = qc_fallspeed_bad_val,
                                           qc_cur_camera_id_was_missing        = False,
                                           qc_cur_camera_img_was_missing       = False,
                                           qc_cur_img_has_no_particle          = True,
                                           qc_all_camera_ids_were_missing      = False,
                                           qc_num_imgs_used_avg_was_missing    = False,
                                           qc_num_imgs_used_avg_less_valid_min = False,
                                           qc_num_imgs_used_avg_less_warn_min  = False)
                particle_data_out_dict['num_objects'].qc_var_ptr[i][cur_camera_id] |= 0x10
                continue

            # temporarily print out the computed values
#            sp.Print(2, '  values: %s', cur_img_anl.GetString("  "))

            # Writes out the data and potentially sets the 5th qc bit that corresponds to particle not passing qc check
            def PerImgDataSetter(var_name, var_val, set_qc_bit, addnl_bits = 0, sub_index = None):
                """ Helper setting variable value and updating its QC bits to set 5th qc bit (option) and addnl_bits.
                    Simply to save space, since all aggregated variables use similar QC and just need to copy data into
                    datastream

                    :param var_name:   string for variable name
                    :param var_val:    value to set that variable to (checks if MISSING_VALUE)
                    :param set_qc_bit: flag to set 5th qc bit
                    :param addnl_bits: additional qc bits to set to (simply ored)
                    :param sub_index:  3rd index for setters (for ROI options)
                """
                # check if value passed in is None
                val_or_none = GetValueOrMissingIfNone(var_val)

                # update aggregated bits to take equality to MISSING_VALUE correctly
                qc_bits_set = addnl_bits
                if set_qc_bit:
                    qc_bits_set |= 0x10

                # set everything
                if sub_index is None:
                    particle_data_out_dict[var_name].var_ptr   [i][cur_camera_id]             = val_or_none
                    particle_data_out_dict[var_name].qc_var_ptr[i][cur_camera_id]            |= qc_bits_set
                else:
                    particle_data_out_dict[var_name].var_ptr   [i][cur_camera_id][sub_index]  = val_or_none
                    particle_data_out_dict[var_name].qc_var_ptr[i][cur_camera_id][sub_index] |= qc_bits_set
            ### end PerImgDataSetter() function ###

            # Goodness check for complexity must be >1, otherwise impossible
            cur_complexity = GetValueOrMissingIfNone(cur_img_anl.complexity)
            if 0 <= cur_complexity < 1:
                sp.Print(1,
                         'Warning: Flake complexity (%f) within image %s < 1. Should be impossible for accepted particles',
                         cur_complexity,
                         img.fileName)

            # Handle this first, so we can properly set qc bits for other per-image properties
            # Test whether particle found within this image is "good" and set QC bit accordingly
            # num_objects != MISSING_VALUE here because we passed check above
            # If we pass quality check, then mark that we found at least one passing image
            num_objects             = GetValueOrMissingIfNone(cur_img_anl.numObjects)
            particle_failed_quality = False
            if cur_img_anl.quality.passedAllChecks:
                no_imgs_have_good_particles = False
            else:
                particle_failed_quality     = True
                num_objects                 = MISSING_VALUE
            PerImgDataSetter('num_objects', num_objects, particle_failed_quality)

            # Copy data into appropriate array locations (in order of appearance in DOD definition
            PerImgDataSetter('maximum_dimension', cur_img_anl.maxDimensionInMM, particle_failed_quality)

            cross_section = GetValueOrMissingIfNone(cur_img_anl.crossSectionInMM2)
            PerImgDataSetter('geometric_cross_section',
                             cross_section,
                             particle_failed_quality,
                             0x20 if cross_section < warn_min_cross_section[0] else 0)

            particle_edge_touch = GetValueOrMissingIfNone(cur_img_anl.edgeTouchInMM)
            PerImgDataSetter('particle_edge_touch',
                             particle_edge_touch,
                             particle_failed_quality,
                             0x20 if particle_edge_touch > warn_max_particle_edge_touch[0] else 0)

            PerImgDataSetter('area_eq_radius', cur_img_anl.areaEquivalentRadiusInMM, particle_failed_quality)
            PerImgDataSetter('perimeter',      cur_img_anl.perimeterInMM,            particle_failed_quality)
            PerImgDataSetter('orientation',    cur_img_anl.orientationInDeg,         particle_failed_quality)
            PerImgDataSetter('aspect_ratio',   cur_img_anl.aspectRatioMinOverMaj,    particle_failed_quality)
            PerImgDataSetter('complexity',     cur_img_anl.complexity,               particle_failed_quality)
            PerImgDataSetter('particle_area',  cur_img_anl.particleAreaInMM2,        particle_failed_quality)

            mean_pixel_intensity = GetValueOrMissingIfNone(cur_img_anl.meanPixelIntensity)
            PerImgDataSetter('mean_pixel_intensity',
                             mean_pixel_intensity,
                             particle_failed_quality,
                             0x20 if mean_pixel_intensity < warn_min_mean_pixel_intensity[0] else 0)

            mean_pixel_intensity_variability = GetValueOrMissingIfNone(cur_img_anl.meanPixelIntensityVariability)
            PerImgDataSetter('mean_pixel_intensity_variability',
                             mean_pixel_intensity_variability,
                             particle_failed_quality,
                             0x20 if mean_pixel_intensity_variability < warn_min_mean_pixel_intensity_variability[0] else 0)

            # Note: focus is checked via round function, so for consistency we will need to do the same here
            # A flake passes focus test if: round(flake_focus * 100) / 100 >= focus_threshold
            roi_focus = GetValueOrMissingIfNone(cur_img_anl.regOfIntFocus)
            PerImgDataSetter('roi_focus',
                             roi_focus,
                             particle_failed_quality,
                             0x20 if (round(roi_focus * 100) / 100.) < warn_min_roi_focus[0] else 0)

            PerImgDataSetter('roi_position', cur_img_anl.regOfIntPositionInMM[0], particle_failed_quality, 0, 0)
            PerImgDataSetter('roi_position', cur_img_anl.regOfIntPositionInMM[1], particle_failed_quality, 0, 1)

            roi_bot_position    = GetValueOrMissingIfNone(cur_img_anl.regOfIntBotLocInMM)
            roi_bot_position_qc = 0
            if roi_bot_position < warn_min_roi_bot_position[0]:
                roi_bot_position_qc |= 0x20
            if roi_bot_position > warn_max_roi_bot_position[0]:
                roi_bot_position_qc |= 0x40
            PerImgDataSetter('roi_bot_position', roi_bot_position, particle_failed_quality, roi_bot_position_qc)

            PerImgDataSetter('roi_half_width_height', cur_img_anl.regOfIntHalfWidthHeightInMM[0], particle_failed_quality, 0, 0)
            PerImgDataSetter('roi_half_width_height', cur_img_anl.regOfIntHalfWidthHeightInMM[1], particle_failed_quality, 0, 1)
        ### end for loop over imgs ###


        # Now per-particle data, aggregated from analyzing per-camera images
        # We need to save quality bits because ClearAllParticleOutputVars will clobber them
        part_anl_avg             = particle_to_process.aggregatedAnalysisResults
        num_imgs_used_for_avg_qc = 0
        num_imgs_used_for_avg    = GetValueOrMissingIfNone(part_anl_avg.numUsedForAverage)
        if no_imgs_have_good_particles:
            num_imgs_used_for_avg_qc |= 0x4
            num_imgs_used_for_avg     = MISSING_VALUE
        if num_imgs_used_for_avg < valid_min_num_imgs_used_avg[0]:
            num_imgs_used_for_avg_qc |= 0x8
        if num_imgs_used_for_avg < warn_min_num_imgs_used_avg [0]:
            num_imgs_used_for_avg_qc |= 0x10
        particle_data_out_dict['num_imgs_used_avg'].var_ptr   [i]  = num_imgs_used_for_avg
        particle_data_out_dict['num_imgs_used_avg'].qc_var_ptr[i] |= num_imgs_used_for_avg_qc

        if num_imgs_used_for_avg < valid_min_num_imgs_used_avg[0] or \
           num_imgs_used_for_avg == MISSING_VALUE:
            ClearAllParticleOutputVars(index          = i,
                                       set_per_camera = False,
                                       set_avg        = True,
                                       camera_id      = None,
                                       qc_fall_speed_is_bad                = qc_fallspeed_bad_val,
                                       qc_cur_camera_id_was_missing        = False,
                                       qc_cur_camera_img_was_missing       = False,
                                       qc_cur_img_has_no_particle          = False,
                                       qc_all_camera_ids_were_missing      = False,
                                       qc_num_imgs_used_avg_was_missing    = (num_imgs_used_for_avg == MISSING_VALUE),
                                       qc_num_imgs_used_avg_less_valid_min = (num_imgs_used_for_avg < valid_min_num_imgs_used_avg[0]),
                                       qc_num_imgs_used_avg_less_warn_min  = (num_imgs_used_for_avg < warn_min_num_imgs_used_avg [0]))
            particle_data_out_dict['num_imgs_used_avg'].var_ptr   [i]  = num_imgs_used_for_avg
            particle_data_out_dict['num_imgs_used_avg'].qc_var_ptr[i] |= num_imgs_used_for_avg_qc
        else:
            # Aggrgate data may be good. We could still have num_imgs_used_for_avg == 1, which will
            # have to be reported within QC. This value is not destructive to data, but may indicate problems
            avg_param_qc = 0
            if num_imgs_used_for_avg == 1:
                avg_param_qc = 0x10

            # Helper to set particle_data_out_dict values
            def ParticleDataAvgSetter(var_name, var_val):
                """ Helper setting variable value and updating its QC bits to avg_param_qc. Simply to save space,
                    since all per-particle variables use the same QC and just need to copy data into datastream

                    :param var_name: string for variable name
                    :param var_val:  value to set that variable to
                """
                # check if value passed in is None
                val_or_none = GetValueOrMissingIfNone(var_val)

                # set things accordingly
                particle_data_out_dict[var_name].var_ptr   [i]  = val_or_none
                particle_data_out_dict[var_name].qc_var_ptr[i] |= avg_param_qc
            ### end function ParticleDataAvgSetter() ###

            # count whether accepted particle may have bad complexity
            if 0 <= part_anl_avg.complexity < 1:
                num_bad_complexity_particles += 1

            ParticleDataAvgSetter('maximum_dimension_avg',                  part_anl_avg.maxDimensionInMM)
            ParticleDataAvgSetter('particle_area_avg',                      part_anl_avg.particleAreaInMM2)
            ParticleDataAvgSetter('area_eq_radius_avg',                     part_anl_avg.areaEquivalentRadiusInMM)
            ParticleDataAvgSetter('perimeter_avg',                          part_anl_avg.perimeterInMM)
            ParticleDataAvgSetter('orientation_avg',                        part_anl_avg.orientationInDeg)
            ParticleDataAvgSetter('aspect_ratio_avg',                       part_anl_avg.aspectRatioMinOverMaj)
            ParticleDataAvgSetter('complexity_avg',                         part_anl_avg.complexity)
            ParticleDataAvgSetter('geometric_cross_section_avg',            part_anl_avg.crossSectionInMM2)
            ParticleDataAvgSetter('mean_pixel_intensity_avg',               part_anl_avg.meanPixelIntensity)
            ParticleDataAvgSetter('mean_pixel_intensity_variability_avg',   part_anl_avg.meanPixelIntensityVariability)

            # when there is only 1 image, analysis should set flatness to None => MISSING_VALUE
            flatness_to_set = part_anl_avg.flatness
            if num_imgs_used_for_avg == 1:
                flatness_to_set = None
            ParticleDataAvgSetter('flatness', flatness_to_set)

            # Add this particle to the list of all particles
            # If we got here, the particle must have passed all quality checks on analysis data
            all_particles.append(particle_to_process)
        ### end check if particle average data is good
    ### end loop over nsamples ###


    # Bin particles
    if skip_time_binning:
        sp.PrintWarning(1, 'Can not bin particles. bin width is set to %f sec, must be in [1, 3600]', bin_width)
    else:
        sp.Print(1, '=======> binning %d particles ====', len(all_particles))

        if len(all_particles) > 0:
            sp.Print(1, '-- particle from %s', all_particles[0].captureDateTime.dateTime.strftime('%Y-%m-%d %H:%M:%S'))
            sp.Print(1, '-- particle to   %s', all_particles[-1].captureDateTime.dateTime.strftime('%Y-%m-%d %H:%M:%S'))

        # try to handle errors that were thrown
        all_bins = None
        try:
            bin_params  = TimeSeriesGenerator.Parameters()
            bin_params.InitFromJSONDict(config_json_dict)

            # print out the parameters before processing just in case
            tmp_bin_dict = bin_params.GetJSONDict()
            sp.Print(1, '=== Binning Parameters ===\n%s\n======', DataAnalysisConfig.GetJSONString([tmp_bin_dict], 3))

            binCreator = TimeSeriesGenerator(bin_params)
            all_bins   = binCreator.AnalyzeParticles(all_particles)
        except Exception as e:
            sp.PrintError(1, 'Error when binning particles\n%s\nTrace:\n%s', e, traceback.format_exc())
            return 0

        # save bins only if we have some
        if all_bins is None:
            # output what possibly went wrong here, since we have 0 bins
            if len(all_particles) == 0:
                becMsg = 'because no particles passed filters for binning'
            else:
                becMsg = 'because no bins received enough enough particles to be statistically significant'
            sp.PrintWarning(1, 'No particle bins were generated %s', becMsg)

        else:
            sp.Print(1, '=======> Generated %d bins ====', len(all_bins))

            # extract time centers for each bin, so we can set output appropriately
            bin_center_times = []
            bin_time_bounds  = []
            bin_cnt          = 0
            for bin in all_bins:
                # check if the bin is good
                if bin.aveFallSpeed is None and \
                   bin.totalNumParticles == 0:
                    continue

                # get bin center time
                center_t = GetGmTimeFromDatetime(bin.binCenter.dateTime)
                bin_center_times.append(center_t)

                # get bin time bounds
                bin_time_bounds.append((center_t + valid_time_bin_offsets[0], center_t + valid_time_bin_offsets[1]))

                sp.Print(1,
                         '-- bin %d, time %s = %s, %d of %d particles averaged',
                         bin_cnt,
                         center_t,
                         bin.binCenter.dateTime,
                         bin.numUsedForAve,
                         bin.totalNumParticles)
                bin_cnt += 1
            ### end loop over all_bins ###

            # allocate time bins output
            timebins_data_out_dict = AllocateOutputData(out_names_dict    = timebins_data_out_names_dict,
                                                        data_stream_str   = MASC_C1_DS_NAME_TIME_BINS,
                                                        num_vals_to_alloc = len(bin_center_times))
            if timebins_data_out_dict is None:
                return -1


            # set bin times correctly
            if len(bin_center_times) > 0:
                # set base time (to GM)
#            dsproc.set_base_time(timebins_output_time_var, 'Base time in Epoch', 0)

#            StatusPrinter('setting times for bins', 1, False, False, status_string)
                time_saved_status = dsproc.set_sample_timevals(timebins_output_time_var, 0, bin_center_times)
                if time_saved_status is 0:
                    sp.PrintError(1, 'Error saving time bins center times')
                    return 0

                for i in range(len(bin_center_times)):
                    bin_bound = bin_time_bounds[i]
                    timebins_data_out_dict['time_bounds'].var_ptr[i][0] = bin_bound[0]
                    timebins_data_out_dict['time_bounds'].var_ptr[i][1] = bin_bound[1]

            # update time unit field attribute to meet CF convention
#            time_units = 'seconds since {0}'.format(time.strftime('%Y-%m-%d:%H:%M:%S', time.gmtime(0)))
#            time_units = 'seconds since 1970-1-1 0:00:00 0:00'
#            status     = dsproc.set_att_value(timebins_output_time_var, 'units', cds.CHAR, time_units)
#            if status == 0:
#                StatusPrinter('Error setting units for time variable in time bins datastream', 1, True, False, status_string)
#                return 0
            del bin_center_times
            del bin_time_bounds

            # copy bin data into datastream
            bin_cnt = -1
            for bin in all_bins:
                # no need to write out bins that are empty
                if bin.aveFallSpeed is None and \
                   bin.totalNumParticles == 0:
                    continue
                bin_cnt += 1

                num_particles_total = GetValueOrMissingIfNone(bin.totalNumParticles)
                timebins_data_out_dict['num_particles_total'].var_ptr   [bin_cnt] = num_particles_total
                timebins_data_out_dict['num_particles_total'].qc_var_ptr[bin_cnt] = 0
                if num_particles_total == MISSING_VALUE:
                    timebins_data_out_dict['num_particles_total'].qc_var_ptr[bin_cnt] |= 0x1
                if num_particles_total == 0:
                    timebins_data_out_dict['num_particles_total'].qc_var_ptr[bin_cnt] |= 0x2

                # Get general QC for all averaged quantities. Bit breakdown:
                # 1. individual quantity set to missing_value
                # 2. num_particles_for_avg == missing_value
                # 3. num_particles_for_avg <  warn_min
                # 4. num_aprticles_for_avg == 0
                agg_bits_avg          = 0
                num_particles_for_avg = GetValueOrMissingIfNone(bin.numUsedForAve)
                timebins_data_out_dict['num_particles_for_avg'].var_ptr   [bin_cnt] = num_particles_for_avg
                timebins_data_out_dict['num_particles_for_avg'].qc_var_ptr[bin_cnt] = 0
                if num_particles_for_avg == MISSING_VALUE:
                    timebins_data_out_dict['num_particles_for_avg'].qc_var_ptr[bin_cnt] |= 0x1
                    agg_bits_avg |= 0x2
                if num_particles_for_avg < warn_min_num_particles_for_avg[0]:
                    timebins_data_out_dict['num_particles_for_avg'].qc_var_ptr[bin_cnt] |= 0x2
                    agg_bits_avg |= 0x4
                if num_particles_for_avg == 0:
                    timebins_data_out_dict['num_particles_for_avg'].qc_var_ptr[bin_cnt] |= 0x4
                    agg_bits_avg |= 0x8
                    ClearAllTimeBinOutputVars(index         = bin_cnt,
                                              set_bin_props = False,
                                              set_bin_avgs  = True,
                                              qc_num_particles_avg_missing   = False,
                                              qc_num_particles_avg_less_warn = (num_particles_for_avg < warn_min_num_particles_for_avg[0]),
                                              qc_num_particles_avg_is0       = True)
                    continue

                # We can continue copying data ONLY if num particles used for average count > 0
                def TimeBinsAvgSetter(var_name, var_val):
                    """ Helper setting variable value and updating its QC bits to agg_bits_avg. Simply to save space,
                        since all aggregated variables use the same QC and just need to copy data into datastream

                        :param var_name: string for variable name
                        :param var_val:  value to set that variable to
                    """
                    # check if value passed in is None
                    val_or_none = GetValueOrMissingIfNone(var_val)

                    # update aggregated bits to take equality to MISSING_VALUE correctly
                    qc_bits_set = agg_bits_avg
                    if val_or_none == MISSING_VALUE:
                        qc_bits_set |= 0x1

                    # set everything
                    timebins_data_out_dict[var_name].var_ptr   [bin_cnt] = val_or_none
                    timebins_data_out_dict[var_name].qc_var_ptr[bin_cnt] = qc_bits_set
                ### end TimeBinsAvgSetter() function ###

                avg_bin_anl = bin.analysisAverage
                TimeBinsAvgSetter('fall_speed_avg',                         bin.aveFallSpeed)
                TimeBinsAvgSetter('maximum_dimension_avg',                  avg_bin_anl.maxDimensionInMM)
                TimeBinsAvgSetter('particle_area_avg',                      avg_bin_anl.particleAreaInMM2)
                TimeBinsAvgSetter('area_eq_radius_avg',                     avg_bin_anl.areaEquivalentRadiusInMM)
                TimeBinsAvgSetter('perimeter_avg',                          avg_bin_anl.perimeterInMM)
                TimeBinsAvgSetter('orientation_avg',                        avg_bin_anl.orientationInDeg)
                TimeBinsAvgSetter('aspect_ratio_avg',                       avg_bin_anl.aspectRatioMinOverMaj)
                TimeBinsAvgSetter('complexity_avg',                         avg_bin_anl.complexity)
                TimeBinsAvgSetter('geometric_cross_section_avg',            avg_bin_anl.crossSectionInMM2)
                TimeBinsAvgSetter('mean_pixel_intensity_avg',               avg_bin_anl.meanPixelIntensity)
                TimeBinsAvgSetter('mean_pixel_intensity_variability_avg',   avg_bin_anl.meanPixelIntensityVariability)
                TimeBinsAvgSetter('flatness_avg',                           avg_bin_anl.flatness)
            ### end for loop over bin_cnt ###
        ### end check for length in all_bins ###
    ### end if else skip_time_binning ###

    # clean up
    del all_bins


    # print out timing information
    profile_num_imgs_inv      = 0
    profile_num_particles_inv = 0
    if profile_num_imgs > 0:
        profile_num_imgs_inv = 1. / profile_num_imgs
    if profile_num_particles > 0:
        profile_num_particles_inv = 1. / profile_num_particles
    profile_elapsed_time      = timeit.default_timer() - profile_time_start
    profile_str = 'Processing finished\n'    \
                  'Run statistics:\n'        \
                  '  - num particles: {0}\n' \
                  '  - num images:    {1}\n' \
                  '  - total time          (sec): {2}\n' \
                  '  - time per particle   (sec): {3}\n' \
                  '  - time per image      (sec): {4}\n' \
                  '  - worst particle time (sec): {5}\n' \
                  '  - worst particle id        : {6}'.format(profile_num_particles,
                                                              profile_num_imgs,
                                                              profile_elapsed_time,
                                                              profile_elapsed_time * profile_num_particles_inv,
                                                              profile_elapsed_time * profile_num_imgs_inv,
                                                              profile_worst_time,
                                                              profile_worst_particle)
    profile_str += '\nNum accepted particles with complexities of [0,1]: {0}'.format(num_bad_complexity_particles)
    sp.Print(1, profile_str)

    # issue warning if we have some particles that have impossible values for complexity
    if num_bad_complexity_particles > 0:
        sp.PrintWarning(1, '%d particles have impossible complexity < 1', num_bad_complexity_particles)


    # -------------------------------------------------------------
    # End algorithm
    # -------------------------------------------------------------

    # Dump contents of output datastructure if running in debug mode
    if dsproc.get_debug_level() > 1:
        dsproc.dump_output_datasets("./debug_dumps", "output_data.debug", 0)

    return 1



#  Main entry function.

#  @param  argc - number of command line arguments
#  @param  argv - command line arguments
#  @return
#    - 0 if successful
#    - 1 if an error occurred

def main():
    import sys
    proc_names = [ "masc_flake_anal" ]
    dsproc.use_nc_extension()

    dsproc.set_init_process_hook(init_process)
    dsproc.set_post_retrieval_hook(post_retrieval_hook)
    dsproc.set_process_data_hook(process_data)
    dsproc.set_finish_process_hook(finish_process)

    exit_value = dsproc.main(
        sys.argv,
        dsproc.PM_RETRIEVER_VAP,
        gVersion,
        proc_names)

    return exit_value

if __name__ == '__main__':
    sys.exit(main())
