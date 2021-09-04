import mp4, bbox, templates, gpmf, fps
import sys, struct, math, io, os, shutil

fin_name = input('Drag the video source file here and press Enter: ')
fin_name = os.path.abspath(fin_name)
basepath = os.path.dirname(fin_name)
basename, _ = os.path.splitext(fin_name)



# make a copy of the source and correct its FPS
ffps_name = basename + '_corrected_fps.mp4'
shutil.copyfile(fin_name, ffps_name)

ffps = open(ffps_name, 'r+b')
numer, denom = fps.get_fps(ffps)
orig_fps = numer / denom

print('Original FPS {} ({}/{})'.format(orig_fps, numer, denom))

# only 30 and 60 fps are supported

if abs(orig_fps - 30) < 3:
    # 30 fps
    target_numer = 30000
    target_denom = 1001
elif  abs(orig_fps - 60) < 5:
    # 60 fps
    target_numer = 60000
    target_denom = 1001
else:
    raise Exception("Unsupported source frame rate")

ffps_orig_name = basename + '_orig_fps.txt'
print('Saving original FPS info into {}'.format(ffps_orig_name))
f = open(ffps_orig_name, 'w')
print(numer, denom, file=f)
f.close()

if t
print('Correcting the frame rate to be GoPRO compatible ({}/{}) ...'.format(target_numer, target_denom))
fps.set_fps(ffps, target_numer, target_denom)


sys.exit()

print(fin_name, basepath, basename)

fbbox = open(sys.argv[1])
fin = open(sys.argv[2], 'rb')

outname = os.path.basename(sys.argv[2])
name, ext = os.path.splitext(outname)
outname = name + '_out.mp4'
fout = open(outname, 'wb')

def parse_time(t):
    t = t.split(':')
    ts = 0
    for i, p in enumerate(reversed(t)):
        ts += float(p) * 60**i
    return ts

if len(sys.argv) > 3:
    bb_offset1, bb_time1, bb_offset2, bb_time2 = map(parse_time, sys.argv[3:3+4])
else:
    bb_offset1 = parse_time(sys.argv[3])
    bb_time1, bb_offset2, bb_time2 = None, None, None

mp4.find_atom(fin, b'moov')
moov = mp4.parse_atom(fin)

fin.seek(0)
mdat_data_size = mp4.find_atom(fin, b'mdat') - mp4.ATOM_HEAD_SIZE
mdat_data_offset = fin.tell() + mp4.ATOM_HEAD_SIZE

#print(moov)
# video_trak = None
# audio_trak = None
# for trak in moov.find(b'trak'):
#     if trak.find(b'vmhd'):
#         video_trak = trak
#     elif trak.find(b'smhd'):
#         audio_trak = trak
# 
# new_moov_children = []
# for child in moov.children:
#     if not (child.key == b'udta' or child.key == b'trak' and child not in (video_trak, audio_trak)):
#         new_moov_children.append(child)
# moov.children = new_moov_children
moov.delete_child(lambda ch: ch.key == b'udta')
moov.delete_child(lambda ch: ch.find(b'gpmd'))

#print(video_trak, audio_trak, gpmf_trak)
print(moov)

video_trak = next(filter(lambda t: t.find(b'vmhd'), moov.find(b'trak')))
video_mdhd = video_trak.find(b'mdhd')[0]
timebase, length = struct.unpack('>II', video_mdhd.data[12:12+8])
num_gpmf_chunks = math.floor(length/timebase/gpmf.CHUNK_TIME)


bbox_time, bbox_gyro = bbox.read(fbbox, -30)
bbox_time = bbox.map_time(bbox_time, bb_offset1, bb_time1, bb_offset2, bb_time2)
bbox_gyro, bbox_time = bbox.map_gyro(bbox_time, bbox_gyro, num_gpmf_chunks, gpmf.CHUNK_TIME, gpmf.GYRO_SAMPLES_PER_CHUNK)
gpmf_chunks = gpmf.make_gpmf(bbox_gyro)

if 0:
    def split_gpmf(f):
        f.seek(0)
        chunks = []
        buf = b''
        while True:
            b = f.read(4)
            
            if not b or b == b'DEVC' and len(buf) > 0:
                chunks.append(buf)
                if not b:
                    break
                buf = b''
            buf += b
        return chunks
    _fmeta = open('meta', 'rb')
    gpmf_chunks = split_gpmf(_fmeta)
    num_gpmf_chunks = len(gpmf_chunks)
    gpmf_chunks = list(map(bytearray, gpmf_chunks))
    # for i, chunk in enumerate(gpmf_chunks):
    #     tick = i*1001
    #     j = 0
    #     while j < len(chunk):
    #         if chunk[j:j+4] == b'TICK':
    #             chunk[j+8: j+12] = struct.pack('>I', tick)
    #             j += 12
    #         else:
    #             j += 1
    for chunk in gpmf_chunks:
        _, g = gpmf.parse(chunk)
        del g.children[-2]
        #print(g)
        #print(g.flatten()
        chunk[:] = g.flatten()
#else:
    #gpmf_chunks = gpmf_chunks[:13]
   # num_gpmf_chunks = len(gpmf_chunks)

gpmf_merged = b''.join(gpmf_chunks)




fout.write(mp4.Atom(b'ftyp', templates.ftyp).flatten())

new_mdat_data_offset = fout.tell() + mp4.ATOM_HEAD_SIZE + len(templates.mdat_gopro_meta)
fout.write(mp4.atom_head(b'mdat', mp4.ATOM_HEAD_SIZE + mdat_data_size + len(templates.mdat_gopro_meta) + len(gpmf_merged) ))
fout.write(templates.mdat_gopro_meta)


fin.seek(mdat_data_offset)
while mdat_data_size:
    chunk_size = min(mdat_data_size, int(10e6))
    fout.write(fin.read(chunk_size))
    mdat_data_size -= chunk_size

gpmf_file_offset = fout.tell()
fout.write(gpmf_merged)

mdat_offset_diff = new_mdat_data_offset - mdat_data_offset
for stco in moov.find(b'stco'):
    count = struct.unpack('>I', stco.data[4:8])[0]
    offset_format = '>{}I'.format(count)
    offsets = struct.unpack(offset_format, stco.data[8:])
    # translate offsets to new origin
    offsets = [o + mdat_offset_diff for o in offsets]
    stco.data[8:] = struct.pack(offset_format, *offsets)


fm = io.BytesIO(templates.meta_trak)
meta_trak = mp4.parse_atom(fm)

gpmf_chunks_sizes = list(map(len, gpmf_chunks))

gpmf_chunks_file_offsets = []
chunk_offset = 0
for l in gpmf_chunks_sizes:
    gpmf_chunks_file_offsets.append(gpmf_file_offset + chunk_offset)
    chunk_offset += l

# set stco - chunk offsets
meta_trak.find(b'stco')[0].data[4:] = struct.pack('>I{}I'.format(num_gpmf_chunks), * [num_gpmf_chunks] + gpmf_chunks_file_offsets)

# set stsz - sample/chunk sizes
meta_trak.find(b'stsz')[0].data[8:] = struct.pack('>I{}I'.format(num_gpmf_chunks), * [num_gpmf_chunks] + gpmf_chunks_sizes)

# set stts - time delta per sample
meta_trak.find(b'stts')[0].data[4:] = struct.pack('>III', 1, num_gpmf_chunks, round(gpmf.CHUNK_TIME*1000))

# set trak duration
meta_trak.find(b'mdhd')[0].data[16:16+4] = struct.pack('>I', num_gpmf_chunks * round(gpmf.CHUNK_TIME*1000))

moov.children.append(meta_trak)

moov.children.insert(1, mp4.Atom(b'udta', templates.udta))

fout.write(moov.flatten())


fmetaout = open('meta2', 'wb')
fmetaout.write(gpmf_merged)