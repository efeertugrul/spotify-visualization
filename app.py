import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from math import pi, isqrt
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import re
from sklearn.preprocessing import MinMaxScaler

st.set_page_config(page_title="Spotify Playlist Visualizer", layout="wide")

# ==================== Spotify Tools Class ====================
class Spotify_Tools:
    
    @staticmethod
    def user_to_playlist_uris(username, sp):
        """returns users playlist uris"""
        playlists = sp.user_playlists(username)
        playlist_uris = []
        while playlists:
            for playlist in playlists['items']:
                x = re.search(r"(?<=spotify:playlist:)(.*)", playlist['uri'])
                if x:
                    playlist_uris.append(x.group(0))
            if playlists['next']:
                playlists = sp.next(playlists)
            else:
                playlists = None
        return playlist_uris

    @staticmethod
    def user_to_playlist_names(username, sp):
        """returns user's playlist names"""
        playlists = sp.user_playlists(username)
        playlist_names = []
        while playlists:
            for playlist in playlists['items']:
                playlist_names.append(playlist['name'])
            if playlists['next']:
                playlists = sp.next(playlists)
            else:
                playlists = None
        return playlist_names
    
    @staticmethod
    def playlist_to_track_ids(playlist_uri, sp):
        """returns track ids in a playlist"""
        response = sp.playlist_items(playlist_uri, 'items.track.id')
        track_list = [x['track']['id'] for x in response['items'] if x['track']]
        return track_list
    
    @staticmethod
    def track_feature(track_id, sp):
        """returns track or tracks audio features"""
        feature_dictionary = sp.audio_features(track_id)
        return feature_dictionary
    
    @classmethod
    def user_to_playlists(cls, username, sp):
        """returns user's playlists as a list"""
        u_playlists = sp.user_playlists(username)
        playlists = []
        playlist_uri = ""
        while u_playlists:
            for playlist in u_playlists['items']:
                x = re.search(r"(?<=spotify:playlist:)(.*)", playlist['uri'])
                if x:
                    playlist_uri = x.group(0)
                    name = playlist['name']
                    playlists.append({"title": name, "song_ids": cls.playlist_to_track_ids(playlist_uri, sp)})
            if u_playlists['next']:
                u_playlists = sp.next(u_playlists)
            else:
                u_playlists = None
        return playlists
    
    @staticmethod
    def track_artists(track_id, sp):
        """returns artists"""
        meta = sp.track(track_id)
        s = ', '
        artist = s.join([singer_name['name'] for singer_name in meta['artists']])
        return artist
    
    @staticmethod
    def track_popularity(track_id, sp):
        """returns popularity"""
        meta = sp.track(track_id)
        return meta["popularity"]
    
    @staticmethod
    def track_n_a_p(track_id, sp):
        """returns name, artists, and popularity as a tuple"""
        meta = sp.track(track_id)
        s = ', '
        artist = s.join([singer_name['name'] for singer_name in meta['artists']])
        return meta["name"], artist, meta["popularity"]
    
    @classmethod
    def generate_track_df(cls, playlists, sp):
        """
        playlists: {'title': str,'song_ids': List[str]}
        """
        all_song_features = []
        for playlist in playlists:
            song_features = cls.track_feature(playlist['song_ids'], sp)
            for song_feature in song_features:
                if song_feature:  # Check if feature is not None
                    name, artist, popularity = Spotify_Tools.track_n_a_p(song_feature['id'], sp)
                    song_feature.update({'playlist': playlist['title'], 'name': name, 'artist': artist, 'popularity': popularity})
                    all_song_features.append(song_feature)
        return pd.DataFrame(all_song_features)


# ==================== Helper Functions ====================
def find_min_sum_n(x):
    """Find optimal grid dimensions for subplots"""
    def factors(x):
        factors_list = []
        for i in range(1, x + 1):
            if x % i == 0:
                factors_list.append(i)
        return factors_list
    
    factor_list = factors(x)
    length = len(factor_list)
    if length % 2 == 0:
        n = int(length / 2)
        return factor_list[n], factor_list[n - 1]
    else:
        n = int(isqrt(x))
        return n, n


def plot_radar(playlist_dfs, columns, music_features):
    """Create radar charts for playlist features"""
    N = len(columns)
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1]
    
    n_df = len(playlist_dfs)
    n_row, n_column = find_min_sum_n(n_df)
    
    fig, axis = plt.subplots(n_row, n_column, figsize=(n_row * 4, n_column * 4), subplot_kw={'projection': 'polar'})
    
    # Handle case where there's only 1 subplot
    if n_row == 1 and n_column == 1:
        axis = [[axis]]
    elif n_row == 1 or n_column == 1:
        axis = [[ax] if n_row == 1 else [ax] for ax in axis]
        if n_row > 1:
            axis = [[a] for a in axis]
    
    for ax_row in axis:
        for ay in ax_row:
            ay.set_axis_off()
    
    x, y = 0, 0
    for dct in playlist_dfs:
        df = dct['df']
        title = dct['title']
        val = list(df.mean())
        val += val[:1]
        
        current_ax = axis[x][y]
        current_ax.plot(angles, val, 'b-', linewidth=2)
        current_ax.fill(angles, val, alpha=0.3)
        current_ax.set_xticks(angles[:-1])
        current_ax.set_xticklabels(columns, size=8)
        current_ax.set_ylim(0, 1)
        current_ax.set_axis_on()
        current_ax.set_title(title, size=10, weight='bold')
        current_ax.grid(True)
        
        y += 1
        if y == n_column:
            y = 0
            x += 1
    
    # Hide unused subplots
    for i in range(len(playlist_dfs), n_row * n_column):
        ax_idx = i % n_column
        row_idx = i // n_column
        axis[row_idx][ax_idx].set_visible(False)
    
    plt.tight_layout()
    return fig


# ==================== Streamlit App ====================
st.title("🎵 Spotify Playlist Visualizer")
st.markdown("Analyze and visualize your Spotify playlists with audio feature analysis.")

# Sidebar for Spotify credentials
st.sidebar.header("🔑 Spotify API Setup")
client_id = st.sidebar.text_input("Spotify Client ID", type="password", help="Get from https://developer.spotify.com/dashboard")
client_secret = st.sidebar.text_input("Spotify Client Secret", type="password")
username = st.sidebar.text_input("Spotify Username", help="Your Spotify username")

# Music features for analysis
music_features = ['danceability', 'energy', 'key', 'loudness', 'mode',
                  'speechiness', 'acousticness', 'instrumentalness',
                  'liveness', 'valence', 'tempo', 'time_signature', 'popularity']

# Min-max scaling values
min_datum = {'acousticness': 0, 'danceability': 0, 'energy': 0,
             'instrumentalness': 0, 'key': -1, 'liveness': 0,
             'loudness': -60, 'mode': 0, 'speechiness': 0,
             'tempo': 0, 'time_signature': 3, 'valence': 0,
             'popularity': 0}
max_datum = {'acousticness': 1, 'danceability': 1, 'energy': 1,
             'instrumentalness': 1, 'key': 11, 'liveness': 1,
             'loudness': 0, 'mode': 1, 'speechiness': 1,
             'tempo': 1015, 'time_signature': 7, 'valence': 1,
             'popularity': 100}

if not (client_id and client_secret and username):
    st.warning("⚠️ Please enter your Spotify API credentials in the sidebar to continue.")
    st.info("""
    **How to get your credentials:**
    1. Go to https://developer.spotify.com/dashboard
    2. Create an app (you'll need a Spotify account)
    3. Copy your Client ID and Client Secret
    4. Enter your Spotify username (from your profile)
    """)
else:
    try:
        # Initialize Spotify client
        client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        
        # Test connection
        user = sp.user(username)
        st.sidebar.success(f"✅ Connected as {user['display_name']}")
        
        # Tab interface
        tab1, tab2, tab3 = st.tabs(["📊 Analysis", "📈 Visualizations", "🎼 Playlist Data"])
        
        with tab1:
            st.header("Playlist Audio Features Analysis")
            
            with st.spinner("Loading your playlists..."):
                playlists = Spotify_Tools.user_to_playlists(username, sp)
            
            if not playlists:
                st.warning("No playlists found. Make sure your playlists are public or you have access to them.")
            else:
                st.success(f"Found {len(playlists)} playlists")
                
                with st.spinner("Generating audio features database..."):
                    df = Spotify_Tools.generate_track_df(playlists, sp)
                
                # Add min-max rows for scaling
                min_max_data = [min_datum, max_datum]
                df = pd.concat([pd.DataFrame(min_max_data), df], ignore_index=True)
                
                st.info(f"Total tracks analyzed: {len(df) - 2}")  # Subtract min/max rows
                
                # Feature statistics
                st.subheader("Feature Statistics")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Select a feature to analyze:**")
                    selected_feature = st.selectbox("Feature", music_features)
                    
                    feature_stats = df[selected_feature].describe()
                    st.write(feature_stats)
                
                with col2:
                    fig, ax = plt.subplots(figsize=(8, 5))
                    df[selected_feature].hist(bins=30, ax=ax, edgecolor='black')
                    ax.set_title(f"{selected_feature.capitalize()} Distribution")
                    ax.set_xlabel(selected_feature.capitalize())
                    ax.set_ylabel("Frequency")
                    st.pyplot(fig)
        
        with tab2:
            st.header("Feature Visualizations")
            
            if 'df' in locals():
                # Scaled data for radar charts
                scaler = MinMaxScaler()
                scaled = scaler.fit_transform(df[music_features])
                scaled_df = pd.DataFrame(columns=music_features, data=scaled)
                
                # Prepare playlists for radar chart
                playlist_titles = df['playlist'].dropna().unique()
                playlist_dfs = []
                
                for title in playlist_titles:
                    scaled_i = scaler.transform(df.loc[df['playlist'] == title][music_features])
                    playlist_dfs.append({'title': title, 'df': pd.DataFrame(scaled_i, columns=music_features)})
                
                if playlist_dfs:
                    st.subheader("Radar Charts - Playlist Feature Profiles")
                    
                    # Select columns for radar chart
                    selected_columns = st.multiselect(
                        "Select features for radar chart",
                        music_features,
                        default=['danceability', 'energy', 'valence', 'acousticness', 'instrumentalness']
                    )
                    
                    if selected_columns:
                        fig = plot_radar(playlist_dfs, selected_columns, music_features)
                        st.pyplot(fig)
                
                # Histograms
                st.subheader("All Features Distribution (Normalized)")
                fig, axes = plt.subplots(5, 3, figsize=(15, 12))
                axes = axes.flatten()
                
                for idx, feature in enumerate(music_features):
                    axes[idx].hist(scaled_df[feature], bins=30, edgecolor='black', alpha=0.7)
                    axes[idx].set_title(feature.capitalize())
                    axes[idx].set_ylabel("Frequency")
                
                axes[-1].set_visible(False)
                plt.tight_layout()
                st.pyplot(fig)
        
        with tab3:
            st.header("Playlist Data")
            
            if 'df' in locals():
                # Playlist selector
                playlist_names = sorted(df['playlist'].dropna().unique())
                selected_playlist = st.selectbox("Select a playlist", playlist_names)
                
                playlist_data = df[df['playlist'] == selected_playlist].drop(columns=['key', 'mode', 'time_signature'])
                st.subheader(f"Tracks in {selected_playlist}")
                st.dataframe(playlist_data[['name', 'artist', 'popularity', 'danceability', 'energy', 'valence', 'acousticness']], 
                            use_container_width=True)
                
                # Download button
                csv = playlist_data.to_csv(index=False)
                st.download_button(
                    label=f"Download {selected_playlist} data as CSV",
                    data=csv,
                    file_name=f"{selected_playlist}.csv",
                    mime="text/csv"
                )
    
    except spotipy.exceptions.SpotifyException as e:
        st.error(f"❌ Spotify API Error: {str(e)}")
        st.info("Check your credentials and try again.")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.info("Make sure your credentials are correct and your profile is public.")
