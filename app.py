import os
import time
from collections import Counter
from math import isqrt

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import spotipy
import streamlit as st
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

    if "streamlit.app" in st.secrets.get("APP_URL", ""):
        redirect_uri = st.secrets.get("APP_URL")
    else:
        redirect_uri = st.secrets.get("REDIRECT_URI", "http://localhost:8501")

    # Added 'user-top-read' to access top artists & tracks
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
        cache_path=None,
    )
    return sp_oauth


def refresh_token_if_needed(sp):
    """Check and refresh token if needed"""
    try:
        sp.current_user()
        return True
    except spotipy.exceptions.SpotifyException as e:
        if "401" in str(e) or "Unauthorized" in str(e):
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
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Count total playlists roughly for progress indicator
        total_playlists = u_playlists.get("total", 50)
        processed = 0

        while u_playlists:
            for playlist in u_playlists["items"]:
                name = playlist["name"]
                playlist_uri = playlist["id"]
                processed += 1

                status_text.text(
                    f"Fetching playlist tracks: {name} ({processed}/{total_playlists})"
                )
                try:
                    tracks_data = Spotify_Tools.playlist_to_tracks(playlist_uri, sp)
                    if tracks_data:
                        playlists.append({"title": name, "tracks": tracks_data})
                except Exception as e:
                    st.warning(f"Could not load playlist '{name}'")
                    continue

                progress_bar.progress(min(processed / total_playlists, 1.0))

            if u_playlists["next"]:
                try:
                    u_playlists = sp.next(u_playlists)
                except:
                    break
            else:
                u_playlists = None

        status_text.empty()
        progress_bar.empty()
        return playlists

    @staticmethod
    def playlist_to_tracks(playlist_id, sp):
        """returns full track items inside a playlist including artist metadata"""
        track_list = []
        try:
            results = sp.playlist_items(playlist_id, limit=100)
        except Exception as e:
            return []

        while results:
            for item in results["items"]:
                if item and item.get("track"):
                    track_list.append(item["track"])

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
                artists.append({"id": item["id"], "name": item["name"]})
            return artists
        except Exception as e:
            st.error(f"Failed to fetch top artists: {str(e)}")
            return []

    @classmethod
    def process_artist_distribution(cls, playlists, top_artists):
        """Calculates distribution of affinity artists within gathered playlists"""
        target_ids = {a["id"] for a in top_artists}
        artist_counts = Counter()
        detailed_records = []

        for playlist in playlists:
            for track in playlist["tracks"]:
                if not track or not track.get("artists"):
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


# ==================== Streamlit App ====================
st.title("Spotify Playlist Visualizer")
st.markdown(
    "Analyze how well your favorite top artists are represented across your playlists."
)

sp_oauth = get_spotify_client()

if not sp_oauth:
    st.error("Missing Spotify API credentials")
else:
    query_params = st.query_params

    if "code" not in query_params and "token_info" not in st.session_state:
        st.info("Click the button below to login with your Spotify account")
        auth_url = sp_oauth.get_authorize_url()
        st.markdown(
            f'<a href="{auth_url}" target="_blank"><button style="padding: 10px 20px; background-color: #1DB954; color: white; border: none; border-radius: 24px; cursor: pointer;">Login with Spotify</button></a>',
            unsafe_allow_html=True,
        )

    elif "code" in query_params and "token_info" not in st.session_state:
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

    elif "token_info" in st.session_state and st.session_state.get("authenticated"):
        token_info = st.session_state["token_info"]

        if token_info.get("expires_at") and token_info["expires_at"] < time.time():
            try:
                token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
                st.session_state["token_info"] = token_info
            except:
                st.warning("Session expired. Please login again.")

        sp = spotipy.Spotify(auth=token_info["access_token"])

        # Layout UI Config
        tab1, tab2, tab3 = st.tabs(
            ["Data Engine", "Affinity Visualizations", "Track Level Insights"]
        )

        with tab1:
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
                limit_artists = st.slider("Top Artist Pool Count", 5, 50, 20, step=5)

            if st.button("Calculate Library Distribution", key="run_pipeline"):
                with st.spinner("Extracting top tier affinities..."):
                    top_artists = Spotify_Tools.get_top_artists_data(
                        sp, time_range=time_range, limit=limit_artists
                    )

                if not top_artists:
                    st.warning("Could not gather user top listening patterns.")
                else:
                    with st.spinner("Processing tracks across your playlists..."):
                        playlists = Spotify_Tools.user_to_playlists(sp)

                    if not playlists:
                        st.warning("No accessible playlists detected.")
                    else:
                        summary_df, detailed_df = (
                            Spotify_Tools.process_artist_distribution(
                                playlists, top_artists
                            )
                        )

                        # Set states strictly inside the successful block
                        st.session_state["summary_df"] = summary_df
                        st.session_state["detailed_df"] = detailed_df
                        st.session_state["playlists_raw"] = playlists
                        st.session_state["current_range"] = time_range
                        st.success("Analysis complete!")

            if "summary_df" in st.session_state:
                st.subheader("Summary Table")
                st.dataframe(st.session_state["summary_df"], use_container_width=True)

        with tab2:
            st.header("Visual Distribution Analysis")

            if "summary_df" in st.session_state:
                summary_df = st.session_state["summary_df"]
                t_window = st.session_state["current_range"].replace("_", " ").title()

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
                    "Go to 'Data Engine' tab and click calculate to populate your visualization profiles."
                )

        with tab3:
            st.header("Playlist Content Breakdown")

            if "detailed_df" in st.session_state:
                detailed_df = st.session_state["detailed_df"]
                playlists_raw = st.session_state["playlists_raw"]

                # Unique playlist names matching what was loaded
                p_names = sorted(
                    list(
                        {
                            track["Playlist Source"]
                            for track in detailed_df.to_dict(orient="records")
                        }
                    )
                )

                selected_playlist = st.selectbox(
                    "Filter Tracks by Your Playlist", ["All"] + p_names
                )

                filtered_df = (
                    detailed_df
                    if selected_playlist == "All"
                    else detailed_df[
                        detailed_df["Playlist Source"] == selected_playlist
                    ]
                )

                st.dataframe(
                    filtered_df[
                        ["Artist Name", "Track Name", "Playlist Source", "Popularity"]
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
                st.info(
                    "Run calculation pipeline under the 'Data Engine' tab to view records."
                )
