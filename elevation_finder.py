import streamlit as st
import requests
import pandas as pd
import time
from typing import List, Tuple, Optional
import io

class USGSElevationFinder:
    def __init__(self):
        """Initialize the ElevationFinder using USGS API"""
        self.api_url = "https://epqs.nationalmap.gov/v1/json"
        
    def get_elevation_usgs(self, lat: float, lon: float, retry_count: int = 3) -> Optional[float]:
        """
        Get elevation using USGS National Map Elevation Point Query Service
        High accuracy for US locations, free, with retry logic
        """
        for attempt in range(retry_count):
            try:
                url = f"{self.api_url}?x={lon}&y={lat}&wkid=4326&units=Feet&includeDate=false"
                response = requests.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'value' in data and data['value'] != -1000000:
                        return float(data['value'])
                    
                # If we got a valid response but no data, don't retry
                if response.status_code == 200:
                    return None
                    
            except requests.exceptions.Timeout:
                if attempt < retry_count - 1:
                    time.sleep(1)  # Wait before retry
                    continue
                return None
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
                st.warning(f"Error for point ({lat}, {lon}): {str(e)}")
                return None
        
        return None

    def get_elevation_for_coordinates(self, coordinates: List[Tuple[float, float]], 
                                     point_ids: List[str] = None) -> pd.DataFrame:
        """Get elevation for multiple coordinate pairs with progress tracking"""
        results = []
        total = len(coordinates)
        
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (lat, lon) in enumerate(coordinates):
            point_id = point_ids[i] if point_ids else f"Point_{i+1}"
            status_text.text(f"Processing {point_id}: ({lat}, {lon}) - {i+1}/{total}")
            
            elevation = self.get_elevation_usgs(lat, lon)
            
            results.append({
                'point_id': point_id,
                'latitude': lat,
                'longitude': lon,
                'elevation_ft': elevation if elevation is not None else 'No Data',
                'status': 'Success' if elevation is not None else 'Failed'
            })
            
            # Update progress
            progress_bar.progress((i + 1) / total)
            
            # Rate limiting - be respectful to USGS
            if i < total - 1:
                time.sleep(0.5)
        
        status_text.text("✅ Processing complete!")
        progress_bar.empty()
        status_text.empty()
        
        return pd.DataFrame(results)

def validate_coordinates(lat: float, lon: float) -> Tuple[bool, str]:
    """Validate coordinate values"""
    if not (-90 <= lat <= 90):
        return False, "Latitude must be between -90 and 90"
    if not (-180 <= lon <= 180):
        return False, "Longitude must be between -180 and 180"
    return True, ""

def main():
    # Page configuration
    st.set_page_config(
        page_title="USGS Elevation Finder",
        page_icon="🏔️",
        layout="wide"
    )
    
    # Header
    st.markdown("""
    <div style="text-align: center; background: linear-gradient(45deg, #1e3c72, #2a5298);
                color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
        <h1>🏔️ USGS Elevation Finder</h1>
        <p style="font-size: 16px; margin: 10px 0;">
            Get accurate elevation data for US locations using USGS National Map API<br>
            <b>Accuracy: ~1.7 feet RMSE</b>
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state for manual points
    if 'manual_points' not in st.session_state:
        st.session_state.manual_points = []
    
    # Mode selection
    st.markdown("### Choose Your Input Method")
    mode = st.radio(
        "Select input mode:",
        ["📍 Manual Input (Individual Points)", "📊 CSV File Upload (Bulk Processing)"],
        label_visibility="collapsed"
    )
    
    if mode == "📍 Manual Input (Individual Points)":
        manual_input_mode()
    else:
        csv_upload_mode()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 14px;">
        <p>Data source: USGS National Map Elevation Point Query Service</p>
        <p>For US locations only. Free tier has rate limits - please be patient.</p>
    </div>
    """, unsafe_allow_html=True)

def manual_input_mode():
    """Manual coordinate input interface"""
    st.markdown("""
    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0;">
        <h3>📍 Manual Input Mode</h3>
        <p>Enter coordinates one by one. Add multiple points, then process all at once.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Input form
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        point_id = st.text_input("Point ID (optional)", key="point_id")
    with col2:
        lat = st.number_input("Latitude", min_value=-90.0, max_value=90.0, 
                             value=0.0, format="%.6f", key="lat")
    with col3:
        lon = st.number_input("Longitude", min_value=-180.0, max_value=180.0, 
                             value=0.0, format="%.6f", key="lon")
    
    # Buttons
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    
    with col1:
        if st.button("➕ Add Point", use_container_width=True):
            # Validate coordinates
            valid, msg = validate_coordinates(lat, lon)
            if not valid:
                st.error(msg)
            elif lat == 0.0 and lon == 0.0:
                st.warning("Please enter non-zero coordinates")
            else:
                pid = point_id if point_id else f"Point_{len(st.session_state.manual_points)+1}"
                st.session_state.manual_points.append({
                    'point_id': pid,
                    'latitude': lat,
                    'longitude': lon
                })
                st.success(f"Added {pid}")
    
    with col2:
        if st.button("🗑️ Clear All", use_container_width=True):
            st.session_state.manual_points = []
            st.rerun()
    
    # Display current points
    if st.session_state.manual_points:
        st.markdown(f"#### 📋 Current Points ({len(st.session_state.manual_points)})")
        df_display = pd.DataFrame(st.session_state.manual_points)
        st.dataframe(df_display, use_container_width=True)
        
        # Process button
        if st.button("🏔️ Get Elevations for All Points", type="primary", use_container_width=True):
            finder = USGSElevationFinder()
            
            coordinates = [(p['latitude'], p['longitude']) for p in st.session_state.manual_points]
            point_ids = [p['point_id'] for p in st.session_state.manual_points]
            
            with st.spinner("Processing elevations..."):
                result_df = finder.get_elevation_for_coordinates(coordinates, point_ids)
            
            # Display results
            st.markdown("### ✅ Results")
            st.dataframe(result_df, use_container_width=True)
            
            # Statistics
            success_count = len(result_df[result_df['status'] == 'Success'])
            failed_count = len(result_df[result_df['status'] == 'Failed'])
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Points", len(result_df))
            col2.metric("Successful", success_count)
            col3.metric("Failed", failed_count)
            
            # Download button
            csv = result_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv,
                file_name="manual_elevations.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.info("👆 Add some points using the form above to get started")

def csv_upload_mode():
    """CSV file upload and processing interface"""
    st.markdown("""
    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0;">
        <h3>📊 CSV Upload Mode</h3>
        <p><b>Required CSV Format:</b> Your CSV should have columns for Point ID, Latitude, and Longitude</p>
        <p><b>Example:</b> point_id, latitude, longitude, other_columns...</p>
    </div>
    """, unsafe_allow_html=True)
    
    # File uploader
    uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])
    
    if uploaded_file is not None:
        try:
            # Read CSV
            df = pd.read_csv(uploaded_file)
            
            st.success(f"✅ File uploaded successfully! ({df.shape[0]} rows, {df.shape[1]} columns)")
            
            # Preview
            st.markdown("#### 👀 Data Preview")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Column selection
            st.markdown("#### 📋 Column Selection")
            columns = list(df.columns)
            
            col1, col2, col3 = st.columns(3)
            
            # Auto-detect columns
            id_col_default = next((col for col in columns if 'id' in col.lower()), columns[0])
            lat_col_default = next((col for col in columns if 'lat' in col.lower()), columns[0])
            lon_col_default = next((col for col in columns if 'lon' in col.lower() or 'lng' in col.lower()), columns[0])
            
            with col1:
                id_col = st.selectbox("Point ID Column", columns, 
                                     index=columns.index(id_col_default) if id_col_default in columns else 0)
            with col2:
                lat_col = st.selectbox("Latitude Column", columns,
                                      index=columns.index(lat_col_default) if lat_col_default in columns else 0)
            with col3:
                lon_col = st.selectbox("Longitude Column", columns,
                                      index=columns.index(lon_col_default) if lon_col_default in columns else 0)
            
            # Validate selections
            if lat_col == lon_col:
                st.error("❌ Latitude and Longitude columns cannot be the same!")
                return
            
            # Process button
            if st.button("🏔️ Process Elevations", type="primary", use_container_width=True):
                try:
                    finder = USGSElevationFinder()
                    
                    # Extract data
                    coordinates = list(zip(df[lat_col], df[lon_col]))
                    point_ids = df[id_col].astype(str).tolist()
                    
                    # Validate coordinates
                    invalid_coords = []
                    for i, (lat, lon) in enumerate(coordinates):
                        valid, msg = validate_coordinates(lat, lon)
                        if not valid:
                            invalid_coords.append((i+1, point_ids[i], msg))
                    
                    if invalid_coords:
                        st.error("❌ Invalid coordinates found:")
                        for row, pid, msg in invalid_coords[:5]:  # Show first 5
                            st.error(f"Row {row} ({pid}): {msg}")
                        if len(invalid_coords) > 5:
                            st.error(f"...and {len(invalid_coords)-5} more")
                        return
                    
                    # Process elevations
                    with st.spinner(f"Processing {len(coordinates)} locations..."):
                        result_df = finder.get_elevation_for_coordinates(coordinates, point_ids)
                    
                    # Merge with original data
                    final_df = df.copy()
                    final_df['elevation_ft'] = result_df['elevation_ft'].values
                    final_df['status'] = result_df['status'].values
                    
                    # Display results
                    st.markdown("### ✅ Processing Complete!")
                    
                    # Statistics
                    success_count = len(result_df[result_df['status'] == 'Success'])
                    failed_count = len(result_df[result_df['status'] == 'Failed'])
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Points", len(result_df))
                    col2.metric("Successful", success_count)
                    col3.metric("Failed", failed_count)
                    
                    # Show results
                    st.markdown("#### 📊 Results Preview")
                    display_cols = [id_col, lat_col, lon_col, 'elevation_ft', 'status']
                    st.dataframe(final_df[display_cols].head(20), use_container_width=True)
                    
                    # Download button
                    csv = final_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Complete Results as CSV",
                        data=csv,
                        file_name="elevations_results.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ Error processing file: {str(e)}")
                    st.exception(e)
        
        except Exception as e:
            st.error(f"❌ Error reading CSV file: {str(e)}")
            st.info("Please make sure your file is a valid CSV format")

if __name__ == "__main__":
    main()
