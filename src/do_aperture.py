import glob
import sys
from tqdm import tqdm
import numpy as np
import logging
import scipy
from read_pht import read_pht_file

# percentage is between 0 and 1
def select_files(the_dir, match_pattern, percentage=1):
    matched_files = glob.glob(the_dir+match_pattern)
    desired_length = max(1, int(len(matched_files) * percentage))
    np.random.seed(42) # for the same percentage, we always get the same selection
    selected_files = np.random.choice(matched_files, size=desired_length, replace=False).tolist()
    return selected_files

def convert_to_aperture_only(apertures):
    return apertures[1::2]

def main(the_dir, match_files='match*.pht', percentage=0.1):
    files = select_files(the_dir, match_files, percentage)
    nrfiles = len(files)
    logging.debug(files)
    # pre process
    apertures = []
    with open(files[0], mode='rb') as file: # b is important -> binary
        fileContent = file.read()
        photheader, apertures, nrstars , _, _ = read_pht_file(files[0], fileContent)
        apertures = convert_to_aperture_only(apertures)
    file.close()
    logging.info(f"Apertures: {apertures}, nr of files: {nrfiles}")
    collect = np.empty([len(apertures), nrstars, nrfiles, 2],dtype=float)
    fwhm = np.empty([nrfiles, 3], dtype=float)
    jd = np.empty([nrfiles], dtype=float)
    # for all files
    for fileidx, entry in enumerate(files):
        fileContent = None
        # open the file for reading
        with open(entry, mode='rb') as file: # b is important -> binary
            fileContent = file.read()
            print(f"{fileidx}/{nrfiles}: {entry}")
            photheader, apertures, nrstars, stars, stardata = read_pht_file(entry, fileContent)
            apertures = convert_to_aperture_only(apertures)
            print("\tDate from header:",photheader.jd, "fwhm:", photheader.fwhm_mean)
            fwhm[fileidx] = [photheader.fwhm_exp, photheader.fwhm_mean, photheader.fwhm_err]
            jd[fileidx] = photheader.jd
            # logging.debug(f"the result is {result[0]}")

            # for every star
            for staridx, starentry in enumerate(stars):
                # for every aperture
                for apidx, aperturedata in enumerate(stardata[staridx]):
                    if aperturedata.mag == 0:
                        print(aperturedata)
                    collect[apidx][starentry.ref_id-1][fileidx] = [aperturedata.mag, aperturedata.err]
                    # collect[apidx][starentry.ref_id-1][fileidx][1] = aperturedata.err
                    if collect[apidx][starentry.ref_id-1][fileidx][0] == 0:
                        print("nul")

    print("Nr of stars for apertureidx 2:", len(collect[2]))
    print("Mb used:", collect.nbytes/1024/1024)
    print("Entry for First aperture, first star:", collect[0][0])
    print("Shape for collect:", collect.shape)
    print(scipy.stats.mstats.describe(np.ma.masked_invalid(collect[2]), axis=0))
    stddevs = np.empty([len(apertures), nrstars])
    counts = np.empty([len(apertures), nrstars])
    import warnings
    warnings.simplefilter('error', UserWarning)
    logging.info("Calculating stddevs...")
    for apidx in tqdm(range(len(collect)), desc="Calculating stddevs"):
        for staridx in range(len(collect[apidx])):
            # print(apidx, staridx)
            masked_collect = np.ma.masked_invalid(collect[apidx][staridx])
            std = masked_collect.std()
            count= masked_collect.count()
            # print("count", count)
            # print("std:", std, type(std), std is np.ma.masked)
            stddevs[apidx, staridx] = std if not std is np.ma.masked else sys.float_info.max
            counts[apidx, staridx] = count

    logging.info(stddevs[0,0:20])
    logging.info(f"Shape for stddevs: {stddevs.shape}")
    logging.info(np.argmin(stddevs[0]))
    # for idx in range(len(stddevs)):
    #     print(stddevs[idx].min(), stddevs[idx].max())
    #     print(idx, stddevs[idx].sum())
    median_erroradded = np.median(np.add(np.take(fwhm, 1, axis=1), np.take(fwhm, 2, axis=1)))
    median_multiply = np.median(np.take(fwhm, 1, axis=1))*1.75

    apertureidx = np.abs(apertures - median_multiply).argmin()
    logging.info(f"FWHM median: {median_multiply} aperture chosen is: {apertures[apertureidx]}")

    compstars_0 = np.argpartition(stddevs[apertureidx], range(3))[:3]

    #compstar_0 = np.argmin(stddevs[apertureidx], axis=0)
    logging.info(f"Compstars_0 with minimum stdev in the chosen aperture: {compstars_0}")
    logging.info(f"Compstars stddev: {stddevs[apertureidx][compstars_0]}")
    logging.info(f"Compstars counts: {counts[apertureidx][compstars_0]}")
    return stddevs, collect, apertures, apertureidx, fwhm, jd, (compstars_0+1).tolist()

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    read_pht_file(sys.argv[1], open(sys.argv[1],'rb').read())
