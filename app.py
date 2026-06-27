import streamlit as st
import pandas as pd
import numpy as np
from math import pi, isqrt
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import re
from sklearn.preprocessing import MinMaxScaler
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Spotify Playlist Visualizer", layout="wide")

# ==================== Spotify OAuth Configuration ====================
def get_spotify_client():
    """Initialize Spotify OAuth client"""
    client_id = st.secrets.get("SPOTIFY_CLIENT_ID") or os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = st.secrets.get("SPOTIFY_CLIENT_SECRET") or os.getenv("SPOTIFY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        return None
    
    # Set redirect URI for Streamlit Cloud or local
    if "streamlit.app" in st.secrets.get("APP_URL", ""):
        redirect_uri = st.secrets.get("APP_URL")
    else:
        redirect_uri = st.secrets.get("REDIRECT_URI", "http://localhost:8501")
    
    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="playlist-read-private playlist-read-collaborative"
    )
    return sp_oauth

# ==================== Spotify Tools Class ====================
class Spotify_Tools:
    
    @staticmethod
    def user_to_playlists(sp):
        """returns user's playlists as a list"""
        u_playlists = sp.current_user_playlists()
        playlists = []
        
        while u_playlists:
            for playlist in u_playlists['items']:
                name = playlist['name']
                playlist_uri = playlist['id']
                try:
                    track_ids = Spotify_Tools.playlist_to_track_ids(playlist_uri, sp)
                    if track_ids:
                        playlists.append({"title": name, "song_ids": track_ids})
                except Exception as e:
                    st.warning(f"Could not load playlist '{name}': {str(e)}")
                    continue
            
            if u_playlists['next']:
                u_playlists = sp.next(u_playlists)
            else:
                u_playlists = None
        
        return playlists
    
    @staticmethod
    def playlist_to_track_ids(playlist_id, sp):
        """returns track ids in a playlist"""
        track_list = []
        results = sp.playlist_items(playlist_id)
        
        while results:
            for item in results['items']:
                if item['track'] and item['track']['id']:
                    track_list.append(item['track']['id'])
            
            if results['next']:
                results = sp.next(results)
            else:
                results = None
        
        return track_list
    
    @staticmethod
    def track_feature(track_ids, sp):
        """returns track audio features"""
        features = []
        # Spotify API limit: 100 tracks per request
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i:i+100]
            features.extend(sp.audio_features(batch))
        return features
    
    @staticmethod
    def track_info(track_id, sp):
        """returns track name, artists, and popularity"""
        try:
            meta = sp.track(track_id)
            s = ', '
            artist = s.join([singer_name['name'] for singer_name in meta['artists']])
            return meta["name"], artist, meta["popularity"]
        except:
            return "Unknown", "Unknown", 0
    
    @classmethod
    def generate_track_df(cls, playlists, sp):
        """Generate dataframe with all track features"""
        all_song_features = []
        progress_bar = st.progress(0)
        
        for idx, playlist in enumerate(playlists):
            try:
                song_features = cls.track_feature(playlist['song_ids'], sp)
                for song_feature in song_features:
                    if song_feature:
                        name, artist, popularity = Spotify_Tools.track_info(song_feature['id'], sp)
                        song_feature.update({
                            'playlist': playlist['title'],
                            'name': name,
                            'artist': artist,
                            'popularity': popularity
                        })
                        all_song_features.append(song_feature)
            except Exception as e:
                st.warning(f"Error processing playlist '{playlist['title']}': {str(e)}")
                continue
            
            progress_bar.progress((idx + 1) / len(playlists))
        
        return pd.DataFrame(all_song_features) if all_song_features else pd.DataFrame()


# ==================== Helper Functions ====================
def find_min_sum_n(x):
    """Find optimal grid dimensions for subplots"""
    def factors(num):
        factors_list = []
        for i in range(1, num + 1):
            if num % i == 0:
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


def plot_radar_plotly(playlist_dfs, columns):
    """Create interactive radar charts using Plotly"""
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set2
    
    for idx, playlist_dict in enumerate(playlist_dfs):
        df = playlist_dict['df']
        title = playlist_dict['title']
        
        values = df[columns].mean().tolist()
        values += values[:1]
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=columns + [columns[0]],
            fill='toself',
            name=title,
            line_color=colors[idx % len(colors)],
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1]
            )
        ),
        showlegend=True,
        height=600,
        hovermode='closest'
    )
    
    return fig


# ==================== Streamlit App ====================
st.title("🎵 Spotify Playlist Visualizer")
st.markdown("Analyze and visualize your Spotify playlists with audio feature analysis.")

# Get OAuth client
sp_oauth = get_spotify_client()

if not sp_oauth:
    st.error("❌ Missing Spotify API credentials")
    st.info("""
    **Setup Required:**
    1. Go to https://developer.spotify.com/dashboard
    2. Create a new app
    3. Add these credentials to Streamlit secrets:
       - SPOTIFY_CLIENT_ID
       - SPOTIFY_CLIENT_SECRET
       - REDIRECT_URI (e.g., https://your-app.streamlit.app)
       - APP_URL (same as REDIRECT_URI)
    """)
else:
    # Check for authorization
    query_params = st.query_params
    
    # Show login button
    if 'code' not in query_params and 'token_info' not in st.session_state:
        st.info("👋 Click the button below to login with your Spotify account")
        
        auth_url = sp_oauth.get_authorize_url()
        st.markdown(f'<a href="{auth_url}" target="_blank"><button style="padding: 10px 20px; background-color: #1DB954; color: white; border: none; border-radius: 24px; cursor: pointer;">🎵 Login with Spotify</button></a>', unsafe_allow_html=True)
    
    elif 'code' in query_params and 'token_info' not in st.session_state:
        # Exchange code for token
        code = query_params['code'][0] if isinstance(query_params['code'], list) else query_params['code']
        
        try:
            with st.spinner("Authenticating..."):
                token_info = sp_oauth.get_access_token(code)
                st.session_state['token_info'] = token_info
                st.session_state['authenticated'] = True
                st.query_params.clear()
                st.rerun()
        except Exception as e:
            st.error(f"❌ Authentication failed: {str(e)}")
    
    elif 'token_info' in st.session_state and st.session_state.get('authenticated'):
        # User is authenticated
        token_info = st.session_state['token_info']
        sp = spotipy.Spotify(auth=token_info['access_token'])
        
        # Get current user
        try:
            current_user = sp.current_user()
            st.sidebar.success(f"✅ Logged in as {current_user['display_name']}")
        except:
            st.sidebar.warning("Session expired. Please login again.")
            if st.sidebar.button("🔄 Login Again"):
                st.session_state.clear()
                st.rerun()
        
        # Logout button
        if st.sidebar.button("🔓 Logout"):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()
        
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
        
        try:
            # Tab interface
            tab1, tab2, tab3 = st.tabs(["📊 Analysis", "📈 Visualizations", "🎼 Playlist Data"])
            
            with tab1:
                st.header("Playlist Audio Features Analysis")
                
                if st.button("🔄 Load Playlists", key="load_playlists"):
                    with st.spinner("Loading your playlists..."):
                        playlists = Spotify_Tools.user_to_playlists(sp)
                    
                    if not playlists:
                        st.warning("No playlists found.")
                    else:
                        st.success(f"Found {len(playlists)} playlists")
                        
                        with st.spinner("Generating audio features database..."):
                            df = Spotify_Tools.generate_track_df(playlists, sp)
                        
                        if not df.empty:
                            # Add min-max rows for scaling
                            min_max_data = [min_datum, max_datum]
                            df = pd.concat([pd.DataFrame(min_max_data), df], ignore_index=True)
                            
                            st.session_state['df'] = df
                            st.session_state['playlists'] = playlists
                            st.success(f"✅ Total tracks analyzed: {len(df) - 2}")
            
            if 'df' in st.session_state:
                df = st.session_state['df']
                playlists = st.session_state['playlists']
                
                # Feature statistics
                st.subheader("Feature Statistics")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Select a feature to analyze:**")
                    selected_feature = st.selectbox("Feature", music_features)
                    
                    feature_stats = df[selected_feature].describe()
                    st.write(feature_stats)
                
                with col2:
                    # Use Plotly instead of matplotlib
                    fig = px.histogram(df, x=selected_feature, nbins=30, title=f"{selected_feature.capitalize()} Distribution")
                    fig.update_traces(marker_line_width=1, marker_line_color='white')
                    st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                st.header("Feature Visualizations")
                
                if 'df' in st.session_state:
                    df = st.session_state['df']
                    playlists = st.session_state['playlists']
                    
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
                            fig = plot_radar_plotly(playlist_dfs, selected_columns)
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # Feature distribution grid
                    st.subheader("All Features Distribution (Normalized)")
                    for i in range(0, len(music_features), 3):
                        cols = st.columns(3)
                        for j, col in enumerate(cols):
                            if i + j < len(music_features):
                                feature = music_features[i + j]
                                fig = px.histogram(scaled_df, x=feature, nbins=20, title=feature.capitalize())
                                with col:
                                    st.plotly_chart(fig, use_container_width=True)
            
            with tab3:
                st.header("Playlist Data")
                
                if 'df' in st.session_state:
                    df = st.session_state['df']
                    
                    # Playlist selector
                    playlist_names = sorted(df['playlist'].dropna().unique())
                    selected_playlist = st.selectbox("Select a playlist", playlist_names)
                    
                    playlist_data = df[df['playlist'] == selected_playlist]
                    
                    st.subheader(f"Tracks in {selected_playlist}")
                    display_cols = ['name', 'artist', 'popularity', 'danceability', 'energy', 'valence', 'acousticness']
                    st.dataframe(playlist_data[display_cols], use_container_width=True)
                    
                    # Download button
                    csv = playlist_data.to_csv(index=False)
                    st.download_button(
                        label=f"📥 Download {selected_playlist} data as CSV",
                        data=csv,
                        file_name=f"{selected_playlist}.csv",
                        mime="text/csv"
                    )
        
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.info("Please try logging in again or check your Spotify account settings.")
