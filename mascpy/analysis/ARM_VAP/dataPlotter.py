# Quickly parses through data output files to build a grid of all time-series data, that then can be plotted

import os
import glob
import time

import matplotlib.dates as dates
import matplotlib.pyplot as plt
from matplotlib.dates import MonthLocator, WeekdayLocator, DateFormatter
from matplotlib.ticker import NullFormatter
import datetime
import numpy as np

checkGoodness = True


def ParseOutputFile(inFile, inVarType):
    # do we have time within?
    haveTimeInName = 'time' in inVarType
    asInt = 'qc_' in inVarType or 'num_' in inVarType

    dataToReturn = []

    with open(inFile) as f:
        firstLine  = True
        timeOffset = 0
        for line in f:
            if line == '\n':
                firstLine = True
                continue

            # for time, we have to add offsets...
            if haveTimeInName and firstLine:
                firstLine  = False
                timeOffset = float(line)
                continue

            toAdd = float(line) + timeOffset
            if asInt:
                toAdd = int(toAdd)
            dataToReturn.append(toAdd)

    return dataToReturn


def InfoFromFileName(inFile):
    fileBase = os.path.basename(inFile)
    inFSplit = fileBase.split('_')

    # data type
    dataType = inFSplit[0]

    # variable
    varName = os.path.splitext(fileBase)[0]
    varName = varName[len(dataType) + 1:]

    return (dataType, varName)


def FlipDictToArray(inDict, isParticle):
    minLen  = 1000000000000000
    for key in inDict:
        print 'key: {0} len {1}'.format(key, len(inDict[key]))
        minLen = min(minLen, len(inDict[key]))

    newData = []
    for i in range(minLen):
        toAdd = {}
        for key in inDict:
            # lump 3x array
            if isParticle and ('_avg' not in key and
                               'time' not in key and
                               'snowflake_fall_speed' not in key and
                               'qc_snowflake_fall_speed' not in key and
                               'flatness' not in key):
                dataToAdd = inDict[key][3*i : 3*(i+1)]
            else:
                dataToAdd = inDict[key][i]
            toAdd[key] = dataToAdd

        # check for goodness
        dataIsGood = True
        if False:
            for key in toAdd:
                if 'qc_' not in key:
                    continue
                val = toAdd[key]
                if val > 0:
                    dataIsGood = False
                    break
        else:
            for key in toAdd:
                val = toAdd[key]

                if checkGoodness:
                    if val == 0 and (
                        key == 'num_particles_total' or
                        key == 'num_particles_for_avg' or
                        key == 'num_imgs_used_avg' or
                        key == 'num_objects'):
                        dataIsGood = False
                        break
                    if key == 'snowflake_fall_speed' and val > 100:
                        dataIsGood = False
                        break
    #
    #             if isinstance(val, list):
    #                 oops = False
    #                 for v2 in val:
    #                     if v2 == -9999:
    #                         dataIsGood = False
    #                         oops       = True
    #                         break
    # #                    if v2 > 1000:
    # #                        dataIsGood = False
    # #                        oops       = True
    # #                        break
    #                 if oops:
    #                     break
    #             else:
    #                 if val == -9999:
    #                     dataIsGood = False
    #                     break
    # #                if val > 1000:
    # #                    dataIsGood = False
    # #                    break

        if dataIsGood or not checkGoodness:
            newData.append(toAdd)
    return newData


def FlipToDict(arrayData):
    # create time x3 repeated
    dataToReturn = {
        'time3': []
    }


    allKeys = [k for k in arrayData[0]]
    for k in allKeys:
        dataToReturn[k] = []

    for v in arrayData:
        for key in v:
            d = v[key]
            if isinstance(d, list):
                for v2 in d:
                    dataToReturn[key].append(v2)
            else:
                dataToReturn[key].append(d)
            if key == 'time':
                dataToReturn['time3'].append(d)
                dataToReturn['time3'].append(d)
                dataToReturn['time3'].append(d)
    return dataToReturn


def CleanUpData(inData, isParticle):
    # are we particles? yes -> time and avg variables have same index. others 3x number

    # iterate over every dictionary element
    for key in inData:
        # delete stuff based on per-particle attributes first
        if isParticle and ('_avg' not in key and 'time' not in key):
            continue

        if 'qc' in key:
            continue

        toCheck = inData[key]

        # iterate through this array
        c = 0
        for v in toCheck:
            # if we're set to missing value, remove this index from ALL other dictionaries
            if v == -9999:
                del toCheck[c]
                for key2 in inData:
                    if key == key2:
                        continue
                    if isParticle:
                        if '_avg' not in key and 'time' not in key:
                            del inData[key2][3 * c + 0]
                            del inData[key2][3 * c + 1]
                            del inData[key2][3 * c + 2]
                        else:
                            del inData[key2][c]
                    else:
                        del inData[key2][c]
            else:
                c += 1


inDir = 'procVals'

allData = {}

if True:
    for f in glob.glob(os.path.join(inDir, '*.txt')):
        print 'file: {0}, {1}'.format(f, InfoFromFileName(f))

        # set up where data will go
        fileInfo = InfoFromFileName(f)
        dataT = fileInfo[0]
        varT  = fileInfo[1]

        if dataT not in allData:
            allData[dataT] = {}
        if varT not in allData[dataT]:
            allData[dataT][varT] = None

        # process
        data = ParseOutputFile(f, varT)
        allData[dataT][varT] = data

    # now clean up our data
    dataArray = {}
    for key in allData:
#        CleanUpData(allData[key], 'particles' in key)
        print '----- {0}'.format(key)
        tmpData = FlipDictToArray(allData[key], 'particles' in key)
        dataArray[key] = tmpData
        print '-='

    # now flip data around to be dictionary of arrays
    dataFlipped = {}
    for key in dataArray:
        tmpData = FlipToDict(dataArray[key])
        dataFlipped[key] = tmpData

    # Let's plot some stuff
    monthsFmt = DateFormatter('%m/%d/%Y')
    for key in dataFlipped:
        data2 = dataFlipped[key]
        time  = [datetime.datetime.fromtimestamp(ts) for ts in data2['time']]
        time3 = [datetime.datetime.fromtimestamp(ts) for ts in data2['time3']]
        for key2 in data2:
            if 'time' in key2 or 'qc' in key2:# or 'avg' not in key2:
                continue
            data = data2[key2]

            plt.figure(1, figsize=(20, 8))

            # definitions for the axes
            left, width = 0.1, 0.65
            bottom, height = 0.1, 0.65
            bottom_h = left_h = left + width + 0.02

            rect_scatter = [left, bottom, width, height]
#            rect_histx = [left, bottom_h, width, 0.2]
            rect_histy = [left_h, bottom, 0.2, height]


#            axHistx = plt.axes(rect_histx)
            axHisty = plt.axes(rect_histy)
            axHisty.yaxis.set_major_formatter(NullFormatter())
            axScatter = plt.axes(rect_scatter)

            if checkGoodness:
                extra = '_filtered'
            else:
                extra = ''

            if not len(time) == len(data):
                axScatter.plot(time3, data, 'o')
            else:
                axScatter.plot(time, data, 'o')

            # remove data thats missing
            dataClean = [x for x in data if x != -9999]

            axHisty.hist(dataClean, bins=100, orientation='horizontal')

            plt.title('{0}: {1} {2}'.format(key, key2, extra))
            axScatter.xaxis.set_major_formatter(monthsFmt)
            axScatter.grid(True)
            axScatter.set_ylim(ymin = 0, ymax = max(data))
            axHisty.set_ylim(ymin = 0, ymax = max(data))

            # show of save
            if False:
                plt.show()
            else:
                saveName = '{0}_{1}{2}.png'.format(key, key2, extra)
                plt.savefig(saveName, bbox_inches='tight')
                plt.close()
#            break



# inFile = 'procVals/timebins_time.txt'
# inFile = 'procVals/timebins_qc_perimeter_avg.txt'
# inFile = 'procVals/timebins_perimeter_avg.txt'
#
# InfoFromFileName(inFile)
#
# print ParseOutputFile(inFile, 'perimeter_avg')
