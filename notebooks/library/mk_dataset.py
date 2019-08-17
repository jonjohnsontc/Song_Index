import argparse
from datetime import date
import glob
import os
from collections import defaultdict

# Not sure why I'm importing dask
# import dask
from dask import dataframe as dd
from dask.distributed import Client
from dask_ml.preprocessing import DummyEncoder, StandardScaler
import pandas as pd 
import numpy as np

from config import paths, non_normalized_cols

# from numba import jit

# need to expose port 8786 in container
# client = Client('scheduler:8786')

def _find_latest_file(path):
    """
    Finds the latest file in a path, based off of a glob string passed
    in 'path'
    """
    # glob hint https://stackoverflow.com/a/39327156
    list_of_files = glob.glob(path)
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


def combine_data(
    songwriter_df_path=paths['songwriter_df_path'], 
    genre_song_dummies_df_path=paths['gs_dummies_path'], 
    pitch_timbre_df_path=paths['segment_path'], 
    song_features_path=paths['song_features_path']
    ):
    """Creates dask dataframe of songs with features ready for modeling"""
    
    list_of_paths = [
        songwriter_df_path,
        genre_song_dummies_df_path,
        pitch_timbre_df_path,
        song_features_path,
    ]
    latest_file_list = list(map(_find_latest_file, list_of_paths))

    songwriter_df = dd.read_csv(latest_file_list[0],
                    # should be pd.Int32Dtype() but running into error
                                dtype = {'IPI': np.float64})\
                        .rename(columns = {'Unnamed: 0' : 'index'})\
                        .set_index('index')
    genre_song_dummies_df = dd.read_csv(latest_file_list[1])\
                            .rename(columns = {'Unnamed: 0' : 'index'})\
                            .set_index('index')
    pitch_timbre_df = dd.read_csv(latest_file_list[2], index_col=False)\
                        .rename(columns = {'Unnamed: 0' : 'track_id'})\
                        .set_index('index')
    song_features_df = dd.read_csv(latest_file_list[3])\
                        .rename(columns = {'Unnamed: 0' : 'index'})\
                        .set_index('index')

    songwriter_and_genres = dd.merge(songwriter_df, 
                                genre_song_dummies_df,
                                on = 'track_id' )
    songwriter_genres_and_pt = dd.merge(songwriter_and_genres,
                                        pitch_timbre_df,
                                        on = 'track_id')
    ready_for_modeling_df = dd.merge(songwriter_genres_and_pt,
                                        song_features_df,
                                        on = 'track_id')
    return ready_for_modeling_df


def mk_song_count_per_songwriter_dict(song_df_with_writer_and_composition_id):
    """Creates a dictionary with writer id's as keys and each of the
    writers songs as values
    """
    songwriter_corpus_dict = defaultdict(set)
    song_dict = song_df_with_writer_and_composition_id.to_dict(orient='index')
    for i in song_dict:
        songwriter_corpus_dict[song_dict[i]['WID']].add(song_dict[i]['CID'])
    return songwriter_corpus_dict


def mk_genre_dummies(genre_song_lookup_df):
    """Creates dummies out of genre to song lookup dataframe"""
    if os.cpu_count() is not None:
        genre_song_lookup_dd = dd.from_pandas(genre_song_lookup_df, 
                                              npartitions=os.cpu_count())
    else:
        genre_song_lookup_dd = dd.from_pandas(genre_song_lookup_df, 
                                              npartitions=16)
    de = DummyEncoder()
    genre_dummies_dd = de.fit_transform(genre_song_lookup_dd)
    return genre_dummies_dd


def rm_non_modeling_feats(ddf, cols_to_drop=non_normalized_cols):
    """Removes features not usable for modeling prior to normalizing
    each songwriter by their avg value
    """
    modeling_feats_only_ddf = ddf.drop(columns=cols_to_drop)
    return modeling_feats_only_ddf, holdover_cols


def mk_avg_sngwrtr_value(ddf):
    """Creates an average song value for each songwriter included in the 
    dataset, and is combined with the original dataset to return a 
    new dask dataframe with said avg values
    """
    grouped_vals_ddf = ddf.groupby('WID').mean()
    return grouped_vals_ddf


def normalize_sngwriter(ddf, how='meanstd'):
    """Normalizes ddf by expression specified in `how`"""
    grouped_vals_ddf = ddf.groupby('WID').transform(lambda x: (x - x.mean()) /\
                                                 x.std() if x.std() is not\
                                                  0 else 0)
    return grouped_vals_ddf


def mk_msong_list(song_list):
    """Retrieve `track_name` and `track_id` for each song and add to 
    separate listing.
    """
    master_song_list = []

    for entry in song_list:
        if isinstance(entry, dict):
            for track in entry['tracks']:
                master_song_list.append(dict({track['name'] : track['id']}))
    return master_song_list


def parse_args():
    """Parses arguments for dataset creation script"""
    
    description = """Script for creating full songwriter dataset prior
    to modeling. 
    """

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("")


def scale_dataset(df):
    # calling dask StandardScaler
    ss = StandardScaler()
    scaled_df = ss.fit_transform(df)
    return scaled_df


def mk_dataset(songwriter_df_path=paths.get('songwriter_df_path'), 
               genre_song_dummies_df_path=paths.get('gs_dummies_path'), 
               pitch_timbre_df_path=paths.get('segment_path'), 
               song_features_path=paths.get('song_features_path'),
               normalize_by='meanstd',):
    """Wrapper function which creates dataset ready for modeling"""
    
    ddf = combine_data(songwriter_df_path,
                       genre_song_dummies_df_path,
                       pitch_timbre_df_path,
                       song_features_path)
    
    # Seems inefficient
    holdover_cols = ddf[[non_normalized_cols]].compute()
    normalized_df = normalize_sngwriter(ddf, how=normalize_by).compute()
    
    combined_df = pd.concat([holdover_cols, normalized_df], axis=1)
    return combined_df


if __name__ == "__main__":
    combined_df = mk_dataset()
    scaled_df = scale_dataset(combined_df)
    scaled_df.to_csv(f"~/data/modeling/scaled_df_{date.today()}")