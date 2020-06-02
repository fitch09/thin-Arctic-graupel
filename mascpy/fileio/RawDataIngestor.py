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


from fileio.DataFileParser import ImageDataParser
from fileio.DataFileParser import FallspeedDataParser
from datatypes.FlakeInfo import FlakeInfo
from datatypes.Enums import EnumParserColumns
import os

class RawDataIngestor(object):
    """ The main job of this injestor is to consume a list of data and image file paths (including file name)
        that were output by the MASC, parse them and aggregate their data into a list hydrometeors.

        As was outlined in Parameters.py, we have to be careful about:
         - hydrometeor data striding folder boundaries. For ex. images are stored in separate folders
         - when acquisition is restarted mid hour, the hydrometeor counter is reset. This means a single
           data output file can have different hydrometeors share indexes (but not time stamps)
    """

    def AggregateHydrometeorData(self, dataInfoFilenames, imageInfoFilenames, imageFilenames = None, dataRange = None):
        """ Creates a list of all particles by parsing data and image info files. This will collate
            everything into particle data structure. If imageFilenames is not None, it is used to
            create full paths to images (since image info only stores image names). If dataRange is
            not None, we limit the particle generation to the dates provided

            :param dataInfoFilenames: list of data info files
            :param imageInfoFilenames: list of image info files
            :param imageFilenames: (opt) list of image filenames to correctly set full image paths
            :param dataRange: (opt)
            :return:
        """
        # Basic check for inputs
        if not dataInfoFilenames or not imageInfoFilenames:
            return None

        # Create parsers
        fallspeedParser = FallspeedDataParser()
        imageParser = ImageDataParser()

        # Parse fallspeed data first
        particles = {}
        for dataFile in dataInfoFilenames:
            localSpeeds = fallspeedParser.ParseFile(dataFile)

            # Parse dictionary to build up full particles based on flake id. If there is an id collision
            # we have to create dictionary based on time stamp. When we parse images, we'll check how
            # close time stamps were.
            for row in localSpeeds:
                particleToAdd = FlakeInfo()
                particleToAdd.SetFallspeed(row)

                # Check if this is the first particle with this id
                flakeId = particleToAdd.flakeId
                if flakeId not in particles:
                    particles[flakeId] = [particleToAdd]

                # Othwerwise, we collided with another index. The time should be different enough
                # so we'll just add it in.
                else:
                    particles[flakeId].append(particleToAdd)

        # Parse image data
        # TODO: handle (and count) errors at this stage, like... missing fallspeeds or missing images?
        for imgFile in imageInfoFilenames:
            localImage = imageParser.ParseFile(imgFile)

            for row in localImage:
                # Check if we can locate a particle with this id
                flakeId = row[EnumParserColumns.FLAKE_ID]
                if flakeId in particles:
                    # Find particle with time close enough (within 1 second) of the index
                    # TODO: do this check... for now let's just lump it into the 1st flake
                    particles[flakeId][0].AddImage(row)

                # Not found -> this means there's no fallspeed for this image...
                # TODO: count. We might have to be careful about correct fallspeed being recorded in the prev file

        # build up a dictionary of image names to their full paths, if we need to
        imgDict = {}
        if imageFilenames is not None:
            for img in imageFilenames:
                filename = os.path.basename(img)
                imgDict[filename] = img

        # Remove any particles that have no images
        # TODO: count. We might have to be careful about having all image files clumped together as part of calling this function
        partIdsToRemove = []
        for partId in particles:
            for p in particles[partId]:
                if len(p.imageData) == 0:
                    particles[partId].remove(p)
                elif imageFilenames is not None:
                    for i in range(0, len(p.imageData)):
                        # TODO: issue warning if a filename is not found in the list...
                        if p.imageData[i].fileName in imgDict:
                            fullPath = imgDict[p.imageData[i].fileName]
                            p.imageData[i].fileName = fullPath

            if len(particles[partId]) == 0:
                partIdsToRemove.append(partId)
        # we can't delete particles inline above since we're iterating over them
        for partId in partIdsToRemove:
            del particles[partId]


        # Convert this dictionary keyed on particle index into a list of particles
        particleList = []
        for partId in particles:
            for p in particles[partId]:
                particleList.append(p)
        del particles

        # Sort if by acquisition time
        sorted(particleList, key=lambda item: item.captureDateTime.dateTime)

        return particleList
