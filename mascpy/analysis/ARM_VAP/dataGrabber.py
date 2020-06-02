# Quickly read through all nc files in a folder and aggregate all data elements within into a text file

import glob, os
import time


def ApplyToFile(inFile, paramToGet, isFloat, outFileToAppend):
    # Calls tis on command line:
    # ncks -s '%f\n' -C -H -v time /data/home/shkurko/data/datastream/oli/olimascparticlesavgM1.c1/olimascparticlesavgM1.c1.20160303.084230.nc > outflile

    if isFloat:
        str = '%f\n'
    else:
        str = '%d\n'

    # if time, figure out what our date was, and write out utc timestamp for it
    base      = os.path.basename(inFile)
    split     = base.split('.')
    date      = split[2]
    timestr   = time.mktime(time.strptime(date, '%Y%m%d'))
    if paramToGet == 'time':
        strToCall = 'echo "{0}" >> {1}'.format(timestr, outFileToAppend)
        os.system(strToCall)

    strToCall = 'ncks -s \'{0}\' -C -H -v {1} {2} >> {3}'.format(str, paramToGet, inFile, outFileToAppend)
    print '      Calling system: {0} -- time {1} {2}'.format(strToCall.replace('\n','\\n'), timestr, date)
    os.system(strToCall)


dataToProcess = [
    {
        'dir': '/data/home/shkurko/data/datastream/oli/olimascparticlesavgM1.c1/',
        'base': 'procVals/timebins',
        'vars': [
            ('time',                                    True),
            ('num_particles_total',                     True), # typo... :/ False),
            ('qc_num_particles_total',                  False),
            ('num_particles_for_avg',                   False),
            ('qc_num_particles_for_avg',                False),
            ('fall_speed_avg',                          True),
            ('qc_fall_speed_avg',                       False),
            ('maximum_dimension_avg',                   True),
            ('qc_maximum_dimension_avg',                False),
            ('particle_area_avg',                       True),
            ('qc_particle_area_avg',                    False),
            ('area_eq_radius_avg',                      True),
            ('qc_area_eq_radius_avg',                   False),
            ('perimeter_avg',                           True),
            ('qc_perimeter_avg',                        False),
            ('orientation_avg',                         True),
            ('qc_orientation_avg',                      False),
            ('aspect_ratio_avg',                        True),
            ('qc_aspect_ratio_avg',                     False),
            ('complexity_avg',                          True),
            ('qc_complexity_avg',                       False),
            ('geometric_cross_section_avg',             True),
            ('qc_geometric_cross_section_avg',          False),
            ('mean_pixel_intensity_avg',                True),
            ('qc_mean_pixel_intensity_avg',             False),
            ('mean_pixel_intensity_variability_avg',    True),
            ('qc_mean_pixel_intensity_variability_avg', False),
            ('flatness_avg',                            True),
            ('qc_flatness_avg',                         False),
        ]
    },
    {
        'dir': '/data/home/shkurko/data/datastream/oli/olimascparticlesM1.c1/',
        'base': 'procVals/particles',
        'vars': [
            ('time',                                    True),
#            ('snowflake_id',                            False),
            ('snowflake_fall_speed',                    True),
            ('qc_snowflake_fall_speed',                 False),
#            ('camera_id',
            ('maximum_dimension',                       True),
            ('qc_maximum_dimension',                    False),
            ('particle_area',                           True),
            ('qc_particle_area',                        False),
            ('particle_edge_touch',                     True),
            ('qc_particle_edge_touch',                  False),
            ('area_eq_radius',                          True),
            ('qc_area_eq_radius',                       False),
            ('perimeter',                               True),
            ('qc_perimeter',                            False),
            ('orientation',                             True),
            ('qc_orientation',                          False),
            ('aspect_ratio',                            True),
            ('qc_aspect_ratio',                         False),
            ('complexity',                              True),
            ('qc_complexity',                           False),
            ('geometric_cross_section',                 True),
            ('qc_geometric_cross_section',              False),
            ('mean_pixel_intensity',                    True),
            ('qc_mean_pixel_intensity',                 False),
            ('mean_pixel_intensity_variability',        True),
            ('qc_mean_pixel_intensity_variability',     False),
            ('roi_focus',                               True),
            ('qc_roi_focus',                            False),
            ('num_objects',                             False),
            ('qc_num_objects',                          False),
#roi_position(time, camera, num_elems_roi_position) ;
#qc_roi_position(time, camera, num_elems_roi_position) ;
            ('roi_bot_position',                        True),
            ('qc_roi_bot_position',                     False),
#roi_half_width_height(time, camera, num_elems_roi_position) ;
#qc_roi_half_width_height(time, camera, num_elems_roi_position) ;
            ('num_imgs_used_avg',                       False),
            ('qc_num_imgs_used_avg',                    False),
            ('maximum_dimension_avg',                   True),
            ('qc_maximum_dimension_avg',                False),
            ('particle_area_avg',                       True),
            ('qc_particle_area_avg',                    False),
            ('area_eq_radius_avg',                      True),
            ('qc_area_eq_radius_avg',                   False),
            ('perimeter_avg',                           True),
            ('qc_perimeter_avg',                        False),
            ('orientation_avg',                         True),
            ('qc_orientation_avg',                      False),
            ('aspect_ratio_avg',                        True),
            ('qc_aspect_ratio_avg',                     False),
            ('complexity_avg',                          True),
            ('qc_complexity_avg',                       False),
            ('geometric_cross_section_avg',             True),
            ('qc_geometric_cross_section_avg',          False),
            ('mean_pixel_intensity_avg',                True),
            ('qc_mean_pixel_intensity_avg',             False),
            ('mean_pixel_intensity_variability_avg',    True),
            ('qc_mean_pixel_intensity_variability_avg', False),
            ('flatness',                                True),
            ('qc_flatness',                             False),
        ]
    }
]


if True:
    for data in dataToProcess:
        # remove all previous output files
        for f in glob.glob(os.path.join('./', '{0}*.txt'.format(data['base']))):
            print 'Cleaning up file: {0}'.format(f)
            os.remove(f)

        for f in glob.glob(os.path.join(data['dir'], '*.nc')):
            print 'File to be processed: {0}'.format(f)

            # run through all parameters
            for param in data['vars']:
                outFile = '{0}_{1}.txt'.format(data['base'], param[0])
                print '  param: {0} -> {1}'.format(param[0], outFile)

                ApplyToFile(f, param[0], param[1], outFile)
    # debugging....
    #            break
    #        break

            print '----'
else:
    fileToLoad = '/data/home/shkurko/data/datastream/oli/olimascparticlesavgM1.c1/olimascparticlesavgM1.c1.20160303.084230.nc'
    ApplyToFile(fileToLoad, 'num_particles_total', True, 'test.txt')

