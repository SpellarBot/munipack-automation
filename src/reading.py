from init_loader import init, settings
import os
import pandas as pd
import numpy as np
import errno
import re
import glob
import logging
import pickle

def read_lightcurve(star,filter=True,preprocess=True, directory=None):
    if directory is None:
        directory = settings.lightcurvedir
    try:
        #print("Reading lightcurve", star, init.lightcurve_dir + 'curve_' + str(star).zfill(5) + '.txt')
        df = pd.read_csv(directory + 'curve_' + str(star).zfill(5) + '.txt', skiprows=[1], sep=' ')
        if(filter):
            df = df[df['V-C'] < 99]
        if(preprocess):
            df = preprocess_lightcurve(df)
        return df
    except OSError as e:
        logging.error(f"OSError for star: {star}, {e}")

def preprocess_lightcurve(df):
    try:
        P = np.percentile(df['V-C'], [5, 95])
        df2 = df[(df['V-C'] > P[0]) & (df['V-C'] < P[1])]
        return df2
    except IndexError:
        logging.error(f"len df: {len(df)}")

def read_pos(star, jd):
    try:
        df = pd.read_csv(settings.posdir + 'pos_' + str(star).zfill(5) + '.txt', skiprows=[1], sep=' ')
        logging.info(df.head())
        df2 = df[df['X'] > 0]
        df3 = df2[df['MAG'] < 99]
        row = df.loc[df['JD'] == jd]
        logging.info(f"reading position, row: {row}, jd: {jd}")
        row = df3.iloc[0]
        return [row['JD'], row['X'],row['Y'], row['MAG']]
        #return (df3['X'].iloc[0], df3['Y'].iloc[0])
        # return df
    except IndexError:
        logging.error("ERROR: IndexError")
        #print("df:",len(df),"df2:", len(df2),"df3:", len(df3))
        logging.error(len(df))


def read_reference_frame():
    file_to_load = settings.basedir + 'reference_frame.txt'
    reference_file = open(file_to_load, 'r')
    reference_file_contents = reference_file.readlines()
    reference_frame=reference_file_contents[0].rstrip()
    reference_frame_index=int(reference_file_contents[1])
    return file_to_load, reference_frame, reference_frame_index


def trash_and_recreate_dir(dir):
    os.system('rm -fr "%s"' % dir)
    #shutil.rmtree(dir, ignore_errors=True)
    create_dir(dir)

def create_dir(dir):
    os.makedirs(dir, exist_ok=True)


# takes a star_list and a dir, and returns a reduced star list - all stars which already have a file in that dir are removed
def reduce_star_list(star_list_1, the_path):
    the_dir = os.listdir(the_path)
    the_dir.sort()
    found = []
    for filename in the_dir:
        found.append(filename_to_star(filename))
    logging.info(f"Found {len(found)} stars already processed in {the_path}")
    return [item for item in star_list_1 if item not in found]

# takes a filename and extracts the star number from it
def filename_to_star(filename):
    m = re.search(r'\d+',filename)
    return int(m.group(0).lstrip('0'))

# read the world positions and return them in a dictionary
# returns {'name': [ra.deg, dec.deg ]}
def read_world_positions(the_path):
    the_dir = os.listdir(the_path)
    the_dir.sort()
    results = {}
    for name in the_dir: # 'file' is a builtin type, 'name' is a less-ambiguous variable name.
        try:
            with open(the_path + name) as f: # No need to specify 'r': this is the default.
                results[filename_to_star(name)] = f.readlines()[0].split(' ')
        except IOError as exc:
            if exc.errno != errno.EISDIR: # Do not fail if a directory is found, just ignore it.
                raise # Propagate other kinds of IOError.
    return results


def read_aperture():
    apertures = np.loadtxt(settings.basedir + 'apertures.txt', dtype=float, delimiter=';')
    apertureidx = np.loadtxt(settings.basedir + 'apertureidx_best.txt', dtype=int)
    aperture = apertures[apertureidx]
    return apertures, apertureidx, aperture

def read_compstars():
    comparison_stars_1 = np.loadtxt(settings.basedir + "comparison_stars_1.txt", dtype=int, delimiter=';')
    with open(settings.basedir + 'comparison_stars_1_desc.bin', 'rb') as compfile:
        comparison_stars_1_desc = pickle.load(compfile)
    return comparison_stars_1, comparison_stars_1_desc

# Select files conforming to the match_pattern using percentage which is between 0 and 1
def file_selector(the_dir, match_pattern, percentage=1):
    matched_files = glob.glob(the_dir+match_pattern)
    desired_length = max(1, int(len(matched_files) * float(percentage)))
    logging.debug(f"Reading.file_selector: {the_dir+match_pattern}, total:{len(matched_files)}, desired:{desired_length}")
    np.random.seed(42) # for the same percentage, we always get the same selection
    selected_files = np.random.choice(matched_files, size=desired_length, replace=False).tolist()
    return selected_files