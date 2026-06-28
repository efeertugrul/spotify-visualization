import os
import time
from collections import Counter

# import numpy as np
from math import isqrt, pi

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import spotipy
import streamlit as st

# import re
from sklearn.preprocessing import MinMaxScaler
from spotipy.oauth2 import SpotifyOAuth

st.set_page_config(page_title="Spotify Playlist Visualizer", layout="wide")


# ==================== Spotify OAuth Configuration ====================
def get_spotify_client():
    """Initialize Spotify OAuth client"""
    client_id = st.secrets.get("SPOTIFY_CLIENT_ID") or os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = st.secrets.get("SPOTIFY_CLIENT_SECRET") or os.getenv(
        "SPOTIFY_CLIENT_SECRET"
    )
    if not client_id or not client_secret:
        return None

    # Set redirect URI for Streamlit Cloud or local
    if "streamlit.app" in st.secrets.get("APP_URL", ""):
        redirect_uri = st.secrets.get("APP_URL")
    else:
        redirect_uri = st.secrets.get("REDIRECT_URI", "http://localhost:8501")

    # Required scopes for full access
    scope = [
        "playlist-read-private",
        "playlist-read-collaborative",
        "user-read-private",
        "user-read-email",
        "user-top-read",
    ]

    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        show_dialog=False,
        cache_path=None,  # Don't cache to file, use session state instead
    )
    return sp_oauth


def refresh_token_if_needed(sp):
    """Check and refresh token if needed"""
    try:
        # Make a simple call to test token validity
        sp.current_user()
        return True
    except spotipy.exceptions.SpotifyException as e:
        if "401" in str(e) or "Unauthorized" in str(e):
            # Token expired, need to re-authenticate
            return False
        return True


# ==================== Spotify Tools Class ====================
class Spotify_Tools:
    @staticmethod
    def user_to_playlists(sp):
        """returns user's playlists as a list"""
        try:
            u_playlists = sp.current_user_playlists(limit=50)
        except Exception as e:
            st.error(f"Failed to load playlists: {str(e)}")
            return []

        playlists = []

        while u_playlists:
            for playlist in u_playlists["items"]:
                name = playlist["name"]
                playlist_uri = playlist["id"]
                try:
                    track_ids = Spotify_Tools.playlist_to_track_ids(playlist_uri, sp)
                    if track_ids:
                        playlists.append({"title": name, "song_ids": track_ids})
                except Exception as e:
                    st.warning(f"Could not load playlist '{name}'")
                    continue

            if u_playlists["next"]:
                try:
                    u_playlists = sp.next(u_playlists)
                except:
                    break
            else:
                u_playlists = None

        return playlists

    @staticmethod
    def playlist_to_track_ids(playlist_id, sp):
        """returns track ids in a playlist"""
        track_list = []
        try:
            results = sp.playlist_items(playlist_id, limit=100)
        except Exception as e:
            st.error(f"Failed to load playlist items: {str(e)}")
            return []

        while results:
            for item in results["items"]:
                if item["track"] and item["track"]["id"]:
                    track_list.append(item["track"]["id"])

            if results["next"]:
                try:
                    results = sp.next(results)
                except:
                    break
            else:
                results = None

        return track_list

    @staticmethod
    def get_top_artists_data(sp, time_range="medium_term", limit=20):
        """Fetches target affinity tier from user's listening data"""
        try:
            results = sp.current_user_top_artists(time_range=time_range, limit=limit)
            artists = []
            for item in results.get("items", []):
                artists.append(
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "image": (item["images"][0]["url"] if item["images"] else None),
                    }
                )
            return artists
        except Exception as e:
            st.error(f"Failed to fetch top artists: {str(e)}")
            return []

    @classmethod
    def process_artist_distribution(cls, playlists, top_artists):
        """Calculates distribution of affinity artists within gathered playlists"""
        target_ids = {a["id"] for a in top_artists}
        artist_counts = Counter()

        # Build cross-reference dictionary tracking which playlist contains which track
        detailed_records = []

        for playlist in playlists:
            for track in playlist["tracks"]:
                if not track.get("artists"):
                    continue
                for artist in track["artists"]:
                    artist_id = artist["id"]
                    if artist_id in target_ids:
                        artist_counts[artist_id] += 1
                        detailed_records.append(
                            {
                                "Artist Name": artist["name"],
                                "Artist ID": artist_id,
                                "Track Name": track.get("name", "Unknown"),
                                "Playlist Source": playlist["title"],
                                "Popularity": track.get("popularity", 0),
                            }
                        )

        # Ensure elements mapping matching top artists order are built
        final_chart_data = []
        for index, artist in enumerate(top_artists):
            final_chart_data.append(
                {
                    "Rank": index + 1,
                    "Artist": artist["name"],
                    "Count": artist_counts[artist["id"]],
                    "Artist ID": artist["id"],
                }
            )

        return pd.DataFrame(final_chart_data), pd.DataFrame(detailed_records)

    @staticmethod
    def track_feature_safe(track_id, sp):
        """DEPRECATED: Spotify API does not support audio features anymore."""
        """Safely get features for a single track"""
        try:
            features = sp.audio_features(track_id)
            if features and features[0]:
                return features[0]
        except:
            pass
        return None

    @staticmethod
    def track_feature(track_ids, sp):
        """DEPRECATED: Spotify API does not support audio features anymore."""
        """returns track audio features with robust error handling"""
        features = []
        failed_count = 0

        # Spotify API limit: 100 tracks per request
        for i in range(0, len(track_ids), 50):  # Reduced batch size for stability
            batch = track_ids[i : i + 50]
            try:
                batch_features = sp.audio_features(batch)
                features.extend([f for f in batch_features if f is not None])
                time.sleep(0.1)  # Small delay between requests
            except spotipy.exceptions.SpotifyException as e:
                if "403" in str(e) or "429" in str(e):
                    # Rate limited or forbidden - try individual requests
                    for track_id in batch:
                        try:
                            feature = Spotify_Tools.track_feature_safe(track_id, sp)
                            if feature:
                                features.append(feature)
                        except:
                            failed_count += 1
                        time.sleep(0.05)
                else:
                    failed_count += len(batch)
            except Exception as e:
                failed_count += len(batch)

        if failed_count > 0:
            st.warning(
                f"Could not fetch audio features for {failed_count} tracks (rate limited or restricted)"
            )

        return features

    @staticmethod
    def track_info(track_id, sp):
        """returns track name, artists, and popularity"""
        try:
            meta = sp.track(track_id)
            s = ", "
            artist = s.join([singer_name["name"] for singer_name in meta["artists"]])
            return meta["name"], artist, meta["popularity"]
        except:
            return "Unknown", "Unknown", 0

    @classmethod
    def generate_track_df(cls, playlists, sp):
        """Generate dataframe with all track features"""
        all_song_features = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, playlist in enumerate(playlists):
            status_text.text(
                f"Processing: {playlist['title']} ({idx + 1}/{len(playlists)})"
            )
            try:
                song_features = cls.track_feature(playlist["song_ids"], sp)

                for song_feature in song_features:
                    if song_feature:
                        try:
                            name, artist, popularity = Spotify_Tools.track_info(
                                song_feature["id"], sp
                            )
                            song_feature.update(
                                {
                                    "playlist": playlist["title"],
                                    "name": name,
                                    "artist": artist,
                                    "popularity": popularity,
                                }
                            )
                            all_song_features.append(song_feature)
                        except:
                            continue
            except Exception as e:
                st.warning(f"Error processing playlist '{playlist['title']}'")
                continue

            progress_bar.progress((idx + 1) / len(playlists))

        status_text.empty()
        progress_bar.empty()
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
        df = playlist_dict["df"]
        title = playlist_dict["title"]

        values = df[columns].mean().tolist()
        values += values[:1]

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=columns + [columns[0]],
                fill="toself",
                name=title,
                line_color=colors[idx % len(colors)],
            )
        )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        showlegend=True,
        height=600,
        hovermode="closest",
    )

    return fig


# ==================== Streamlit App ====================
st.title("Spotify Playlist Visualizer")
# st.markdown("Analyze and visualize your Spotify playlists with audio feature analysis.")
st.markdown(
    "Analyze how well your favorite top artists are represented across your playlists."
)

# Get OAuth client
sp_oauth = get_spotify_client()

if not sp_oauth:
    st.error("Missing Spotify API credentials")
    st.info("""
    Setup Required:
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
    if "code" not in query_params and "token_info" not in st.session_state:
        st.info("Click the button below to login with your Spotify account")

        auth_url = sp_oauth.get_authorize_url()
        st.markdown(
            f'<a href="{auth_url}" target="_blank"><button style="padding: 10px 20px; background-color: #1DB954; color: white; border: none; border-radius: 24px; cursor: pointer;">Login with Spotify</button></a>',
            unsafe_allow_html=True,
        )

    elif "code" in query_params and "token_info" not in st.session_state:
        # Exchange code for token
        code = (
            query_params["code"][0]
            if isinstance(query_params["code"], list)
            else query_params["code"]
        )

        try:
            with st.spinner("Authenticating..."):
                token_info = sp_oauth.get_access_token(code)
                st.session_state["token_info"] = token_info
                st.session_state["authenticated"] = True
                st.query_params.clear()
                st.rerun()
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            if st.button("Try Again"):
                st.session_state.clear()
                st.rerun()

    elif "token_info" in st.session_state and st.session_state.get("authenticated"):
        # User is authenticated
        token_info = st.session_state["token_info"]

        # Refresh token if expired
        if token_info.get("expires_at") and token_info["expires_at"] < time.time():
            try:
                token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
                st.session_state["token_info"] = token_info
            except:
                st.warning("Session expired. Please login again.")
                if st.button("Login Again"):
                    st.session_state.clear()
                    st.rerun()

        sp = spotipy.Spotify(auth=token_info["access_token"])

        # Get current user
        try:
            current_user = sp.current_user()
            st.sidebar.success(f"Logged in as {current_user['display_name']}")
        except Exception as e:
            st.sidebar.warning("Session expired. Please login again.")
            if st.sidebar.button("Login Again"):
                st.session_state.clear()
                st.rerun()

        # Logout button
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

        # Music features for analysis
        # music_features = [
        #     "danceability",
        #     "energy",
        #     "key",
        #     "loudness",
        #     "mode",
        #     "speechiness",
        #     "acousticness",
        #     "instrumentalness",
        #     "liveness",
        #     "valence",
        #     "tempo",
        #     "time_signature",
        #     "popularity",
        # ]

        # Min-max scaling values
        # min_datum = {
        #     "acousticness": 0,
        #     "danceability": 0,
        #     "energy": 0,
        #     "instrumentalness": 0,
        #     "key": -1,
        #     "liveness": 0,
        #     "loudness": -60,
        #     "mode": 0,
        #     "speechiness": 0,
        #     "tempo": 0,
        #     "time_signature": 3,
        #     "valence": 0,
        #     "popularity": 0,
        # }
        # max_datum = {
        #     "acousticness": 1,
        #     "danceability": 1,
        #     "energy": 1,
        #     "instrumentalness": 1,
        #     "key": 11,
        #     "liveness": 1,
        #     "loudness": 0,
        #     "mode": 1,
        #     "speechiness": 1,
        #     "tempo": 1015,
        #     "time_signature": 7,
        #     "valence": 1,
        #     "popularity": 100,
        # }

        try:
            # Tab interface
            # tab1, tab2, tab3 = st.tabs(["Analysis", "Visualizations", "Playlist Data"])
            tab1, tab2, tab3 = st.tabs(
                ["Data Engine", "Affinity Visualizations", "Track Level Insights"]
            )
            with tab1:
                # st.header("Playlist Audio Features Analysis")
                st.header("Affinity Calculation Pipeline")

                col_range, col_lim = st.columns(2)
                with col_range:
                    time_range = st.selectbox(
                        "Select Listening History Window",
                        options=["short_term", "medium_term", "long_term"],
                        index=1,
                        format_func=lambda x: {
                            "short_term": "Short Term (~4 Weeks)",
                            "medium_term": "Medium Term (~6 Months)",
                            "long_term": "Long Term (~Years)",
                        }[x],
                    )
                with col_lim:
                    limit_artists = st.slider(
                        "Top Artist Pool Count", 5, 50, 20, step=1
                    )

                if st.button("Calculate Library Distribution", key="run_pipeline"):
                    with st.spinner("Step 1: Extracting top tier affinities..."):
                        top_artists = Spotify_Tools.get_top_artists_data(
                            sp, time_range=time_range, limit=limit_artists
                        )

                    if not top_artists:
                        st.warning("Could not gather user top listening patterns.")
                    else:
                        with st.spinner(
                            "Step 2: Processing libraries & cataloging playlist metrics..."
                        ):
                            playlists = Spotify_Tools.user_to_playlists(sp)

                        if not playlists:
                            st.warning("No accessible playlists detected.")
                        else:
                            summary_df, detailed_df = (
                                Spotify_Tools.process_artist_distribution(
                                    playlists, top_artists
                                )
                            )

                            st.session_state["summary_df"] = summary_df
                            st.session_state["detailed_df"] = detailed_df
                            st.session_state["current_range"] = time_range
                            st.success("Analysis complete!")

                if "summary_df" in st.session_state:
                    st.subheader("High-Level Metrics")
                    st.dataframe(
                        st.session_state["summary_df"], use_container_width=True
                    )
                # if st.button("Load Playlists", key="load_playlists"):
                #     with st.spinner("Loading your playlists..."):
                #         playlists = Spotify_Tools.user_to_playlists(sp)

                #     if not playlists:
                #         st.warning(
                #             "No playlists found. Make sure you have public playlists."
                #         )
                #     else:
                #         st.success(f"Found {len(playlists)} playlists")

                #         with st.spinner("Generating audio features database..."):
                #             df = Spotify_Tools.generate_track_df(playlists, sp)

                #         if not df.empty:
                #             # Add min-max rows for scaling
                #             min_max_data = [min_datum, max_datum]
                #             df = pd.concat(
                #                 [pd.DataFrame(min_max_data), df], ignore_index=True
                #             )

                #             st.session_state["df"] = df
                #             st.session_state["playlists"] = playlists
                #             st.success(f"Total tracks analyzed: {len(df) - 2}")
                #         else:
                #             st.warning(
                #                 "No audio features could be extracted. This may be due to API rate limiting."
                #             )

            with tab2:
                st.header("Visual Distribution Analysis")

                if "summary_df" in st.session_state:
                    summary_df = st.session_state["summary_df"]
                    t_window = (
                        st.session_state["current_range"].replace("_", " ").title()
                    )

                    fig = px.bar(
                        summary_df,
                        x="Artist",
                        y="Count",
                        color="Count",
                        text="Count",
                        hover_data=["Rank"],
                        labels={
                            "Count": "Tracks Found in Playlists",
                            "Artist": "Top Artists (Ordered by Affinity)",
                        },
                        title=f"Playlist Volume Distribution for Your Top Artists ({t_window})",
                        color_continuous_scale=px.colors.sequential.Viridis,
                    )

                    fig.update_traces(textposition="outside")
                    fig.update_layout(
                        xaxis={"categoryorder": "trace"},
                        height=600,
                        margin=dict(t=50, b=100),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(
                        "Run calculation execution inside 'Data Engine' to populate visual insights."
                    )

            with tab3:
                st.header("Playlist Content Breakdown")

                if "detailed_df" in st.session_state:
                    detailed_df = st.session_state["detailed_df"]

                    artist_filter = sorted(detailed_df["Artist Name"].unique())
                    selected_artist = st.selectbox(
                        "Filter Tracks by Artist", ["All"] + artist_filter
                    )

                    filtered_df = (
                        detailed_df
                        if selected_artist == "All"
                        else detailed_df[detailed_df["Artist Name"] == selected_artist]
                    )

                    st.dataframe(
                        filtered_df[
                            [
                                "Artist Name",
                                "Track Name",
                                "Playlist Source",
                                "Popularity",
                            ]
                        ],
                        use_container_width=True,
                    )

                    csv = filtered_df.to_csv(index=False)
                    st.download_button(
                        label="Download Filtered Matches to CSV",
                        data=csv,
                        file_name="matched_playlist_tracks.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("No compiled tracking records found.")
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("Please try logging in again.")
