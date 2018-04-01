from functools import partial

import init
import reading
#import astropy_helper
import matplotlib as mp
mp.use('Agg') # needs no X server
import matplotlib.pyplot as plt
import seaborn as sns
import multiprocessing as mp
import tqdm
import numpy as np
from astropy.coordinates import SkyCoord
from gatspy.periodic import LombScargleFast
import init
import star_description
from reading import trash_and_recreate_dir

TITLE_PAD=40

def set_seaborn_style():
    sns.set_context("notebook", font_scale=4)
    sns.set_style("ticks")

# takes:  [ {'id': star_id, 'match': {'name': match_name, 'separation': separation_deg  } } ]
def plot_lightcurve(tuple, comparison_stars):
#    try:
    star_description = tuple[0]
    curve = tuple[1]
    star = star_description.local_id
    star_match, separation = star_description.get_match_string(star_description)
    upsilon_text = star_description.get_upsilon_string(star_description)
    coord = star_description.coords
    if(curve is None):
        print("Curve is None for star", star)
        return
    curve = curve.replace(to_replace=99.99999, value=np.nan, inplace=False)

    curve2_norm = curve
    curve2_norm['V-C'] = curve['V-C'] + comparison_stars[0].vmag

    used_curve = curve2_norm
    used_curve_max = curve2_norm['V-C'].max()
    used_curve_min = curve2_norm['V-C'].min()

    #insert counting column
    used_curve.insert(0, 'Count', range(0, len(used_curve)))
    g = sns.lmplot('Count', 'V-C',
               data=used_curve, size=20, aspect=5,scatter_kws={"s": 15},
               fit_reg=False)
    star_name = '' if star_match == '' else " ({} - dist:{:.4f})".format(star_match, separation)
    plt.title("Star {0}{1}, position: {2}{3}".format(star, star_name, get_hms_dms(coord), upsilon_text), pad=TITLE_PAD)

    #plt.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))
    #plt.set_title("Custom tick formatter")
    #fig.autofmt_xdate()
    plt.xlabel('Count', labelpad=TITLE_PAD)
    plt.ylabel("Absolute Mag, comp star = {:2.2f}".format(comparison_stars[0].vmag), labelpad=TITLE_PAD)
    plot_max = used_curve_max
    plot_min = min(plot_max-1, used_curve_min)
    print('min', plot_min, 'max', plot_max, 'usedmin', used_curve_min, 'usedmax', used_curve_max)
    if np.isnan(plot_max) or np.isnan(plot_min):
        print("star is nan", star)
        return
    #print("Star:{},dim:{},bright:{}".format(star, plot_dim, plot_bright))
    plt.ylim(plot_min,plot_max)
    plt.xlim(0, len(used_curve))
    plt.gca().invert_yaxis()
    #g.map(plt.errorbar, 'Count', 'V-C', yerr='s1', fmt='o')
    #plt.ticklabel_format(style='plain', axis='x')
    g.savefig(init.chartsdir+str(star).zfill(5) )
    plt.close(g.fig)
#    except:
#        print("error", tuple)

def plot_phase_diagram(tuple, comparison_stars, suffix='', period=None):
    star_description = tuple[0]
    curve = tuple[1]
    star = star_description.local_id
    star_match, separation = star_description.get_match_string(star_description)
    upsilon_text = star_description.get_upsilon_string(star_description)
    match_string = "({})".format(star_match) if not star_match == '' else ''
    print("Calculating phase diagram for", star)
    if curve is None:
        print("Curve of star {} is None".format(star))
        return
    t_np = curve['JD'].as_matrix()
    y_np = curve['V-C'].as_matrix()
    dy_np = curve['s1'].as_matrix()
    if period is None:
        ls = LombScargleFast()
        period_max = np.max(t_np)-np.min(t_np)
        ls.optimizer.period_range = (0.01,period_max)
        ls.fit(t_np,y_np)
        period = ls.best_period
    print("Best period: " + str(period) + " days")
    fig=plt.figure(figsize=(18, 16), dpi= 80, facecolor='w', edgecolor='k')
    plt.xlabel("Phase", labelpad=TITLE_PAD)
    plt.ylabel("Magnitude", labelpad=TITLE_PAD)
    plt.title("Star {} {}, period: {:.5f} d{}".format(star, match_string, period, upsilon_text), pad=TITLE_PAD)
    plt.tight_layout()
    # plotting + calculation of 'double' phase diagram from -1 to 1
    phased_t = np.fmod(t_np/period,1)
    minus_one = lambda t: t - 1
    minus_oner = np.vectorize(minus_one)
    phased_t2 = minus_oner(phased_t)
    phased_lc = y_np[:]
    phased_t_final = np.append(phased_t2, phased_t)
    phased_lc_final = np.append(phased_lc, phased_lc)
    phased_lc_final = phased_lc_final + comparison_stars[0].vmag
    phased_err = np.append(dy_np, dy_np)
    plt.gca().invert_yaxis()
    plt.errorbar(phased_t_final,phased_lc_final,yerr=phased_err,linestyle='none',marker='o', ecolor='gray', elinewidth=1)
    fig.savefig(init.phasedir+'phase'+str(star).zfill(5)+suffix)
    plt.close(fig)

def get_hms_dms(coord):
    return "{:2.0f}$^h$ {:02.0f}$^m$ {:02.2f}$^s$ | {:2.0f}$\degree$ {:02.0f}$'$ {:02.2f}$''$"\
        .format(coord.ra.hms.h, abs(coord.ra.hms.m), abs(coord.ra.hms.s),
                coord.dec.dms.d, abs(coord.dec.dms.m), abs(coord.dec.dms.s))

def format_date(x, pos=None):
    thisind = np.clip(int(x + 0.5), 0, N - 1)
    return r.date[thisind].strftime('%Y-%m-%d')

def read_lightcurves(star_pos, star_descriptions):
    star_description = star_descriptions[star_pos]
    try:
        tuple = star_description, reading.read_lightcurve(star_description.local_id,filter=False)
        return tuple
    except FileNotFoundError:
        print("File not found error in store and curve for star", star_description.local_id)

# reads lightcurves and passes them to lightcurve plot or phase plot
def run(star_descriptions, comparison_stars, do_charts, do_phase):
    CHUNK = 10
    # star_list = [star.local_id for star in star_descriptions]
    star_list = range(0, len(star_descriptions))
    lightcurves = []
    set_seaborn_style()
    pool = mp.Pool(init.nr_threads)

    print("Reading star positions, total size = ",len(star_list))
    func = partial(read_lightcurves, star_descriptions=star_descriptions)
    for _ in tqdm.tqdm(pool.imap_unordered(func, star_list, CHUNK), total=len(init.all_star_list)):
        lightcurves.append(_)
        pass

    if do_charts:
        print("Plotting lightcurve, total size = ",len(lightcurves))
        trash_and_recreate_dir(init.chartsdir)
        func = partial(plot_lightcurve, comparison_stars=comparison_stars)
        for _ in tqdm.tqdm(pool.imap_unordered(func, lightcurves, CHUNK), total=len(lightcurves)):
            pass

    if do_phase:
        print("Plotting phase diagrams, total size = ",len(lightcurves))
        trash_and_recreate_dir(init.phasedir)
        func = partial(plot_phase_diagram, comparison_stars=comparison_stars)
        for _ in tqdm.tqdm(pool.imap_unordered(func, lightcurves, CHUNK), total=len(lightcurves)):
            pass
