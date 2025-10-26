import sys
import os
import pathlib

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from sqlalchemy import text
from logging_config import setup_logging
from db_handler import get_update_time, read_df
from doctrines import create_fit_df, get_all_fit_data
from config import DatabaseConfig
# Insert centralized logging configuration
logger = setup_logging(__name__, log_file="doctrine_status.log")
mkt_db = DatabaseConfig("wcmkt")

@st.cache_data(ttl=600, show_spinner="Loading cacheddoctrine fits...")
def get_fit_summary()->pd.DataFrame:
    """Get a summary of all doctrine fits"""
    logger.info("Getting fit summary")

    # Get the raw data with all fit details
    all_fits_df, _ = create_fit_df()

    if all_fits_df.empty:
        return pd.DataFrame()

    # Get unique fit_ids
    fit_ids = all_fits_df['fit_id'].unique()

    # Create a summary dataframe
    fit_summary = []

    for fit_id in fit_ids:
        # Filter data for this fit
        try:
            fit_data = all_fits_df[all_fits_df['fit_id'] == fit_id]

        except Exception as e:
            st.error("Error getting fit data for fit_id: " + fit_id + " " + str(e))
            logger.error(f"Error: {e}")
            continue
        # Get the first row for fit metadata
        first_row = fit_data.iloc[0]

        # Get basic information
        ship_id = first_row['ship_id']
        ship_name = first_row['ship_name']
        hulls = first_row['hulls'] if pd.notna(first_row['hulls']) else 0

        # Extract ship group from the data
        ship_group = "Ungrouped"  # Default

        # Find the row that matches the ship_id
        ship_rows = fit_data[fit_data['type_id'] == ship_id]

        # Check if ship_rows is not empty and has a 'group_name' column
        if not ship_rows.empty and 'group_name' in ship_rows.columns:
            try:
                # Get the first row's group_name value
                ship_group = ship_rows['group_name'].iloc[0]
            except Exception as e:
                logger.error(f"Error getting group_name for fit_id: {fit_id}: {e}")
                continue

        # Calculate minimum fits (how many complete fits can be made)
        try:
            min_fits = fit_data['fits_on_mkt'].min()
            # Handle NaN values
            if pd.isna(min_fits):
                min_fits = 0
        except Exception as e:
            logger.error(f"Error getting min_fits for fit_id: {fit_id}: {e}")
            continue

        # Get target value from database if available, otherwise use default
        target = get_ship_target(0, fit_id)

        # Calculate target percentage
        if target > 0:
            target_percentage = min(100, int((min_fits / target) * 100))
        else:
            target_percentage = 0

        # Get the lowest stocked modules (exclude the ship itself)
        ship_type_id = first_row['ship_id']
        module_data = fit_data[fit_data['type_id'] != ship_type_id]
        lowest_modules = module_data.sort_values('fits_on_mkt').head(3)

        lowest_modules_list = []
        for _, row in lowest_modules.iterrows():
            module_name = row['type_name']
            module_stock = row['fits_on_mkt']
            if not pd.isna(module_name) and not pd.isna(module_stock):
                lowest_modules_list.append(f"{module_name} ({int(module_stock)})")

        # Get daily average volume if available
        daily_avg = fit_data['avg_vol'].mean() if 'avg_vol' in fit_data.columns else 0

        # Get fit name from the ship_targets table if available
        fit_name = get_fit_name(fit_id)

        # Add to summary list
        fit_summary.append({
            'fit_id': fit_id,
            'ship_id': ship_id,
            'ship_name': ship_name,
            'fit': fit_name,
            'ship': ship_name,
            'fits': min_fits,
            'hulls': hulls,
            'target': target,
            'target_percentage': target_percentage,
            'lowest_modules': lowest_modules_list,
            'daily_avg': daily_avg,
            'ship_group': ship_group
        })

    return pd.DataFrame(fit_summary)

def format_module_list(modules_list):
    """Format the list of modules for display"""
    if not modules_list:
        return ""
    return "<br>".join(modules_list)

def get_fit_name(fit_id: int) -> str:
    """Get the fit name for a given fit id"""
    try:
        df = read_df(mkt_db, text("SELECT fit_name FROM ship_targets WHERE fit_id = :fit_id"), {"fit_id": fit_id})
        return str(df.loc[0, 'fit_name']) if not df.empty else "Unknown Fit"
    except Exception as e:
        logger.error(f"Error getting fit name for fit_id: {fit_id}")
        logger.error(f"Error: {e}")
        return "Unknown Fit"

def get_module_stock_list(module_names: list):
    """Get lists of modules with their stock quantities for display and CSV export."""

    #set the session state variables for the module list and csv module list
    if not st.session_state.get('module_list_state'):
        st.session_state.module_list_state = {}
    if not st.session_state.get('csv_module_list_state'):
        st.session_state.csv_module_list_state = {}

    for module_name in module_names:
        if module_name not in st.session_state.module_list_state:
            logger.info(f"Querying database for {module_name}")
            query = text(
                """
                SELECT type_name, type_id, total_stock, fits_on_mkt
                FROM doctrines
                WHERE type_name = :module_name
                LIMIT 1
                """
            )
            df = read_df(mkt_db, query, {"module_name": module_name})
            if not df.empty and pd.notna(df.loc[0, 'total_stock']) and pd.notna(df.loc[0, 'fits_on_mkt']) and pd.notna(df.loc[0, 'type_id']):
                module_info = f"{module_name} (Total: {int(df.loc[0, 'total_stock'])} | Fits: {int(df.loc[0, 'fits_on_mkt'])})"
                csv_module_info = f"{module_name},{int(df.loc[0, 'type_id'])},{int(df.loc[0, 'total_stock'])},{int(df.loc[0, 'fits_on_mkt'])}\n"
            else:
                module_info = f"{module_name}"
                csv_module_info = f"{module_name},0,0,0\n"

            st.session_state.module_list_state[module_name] = module_info
            st.session_state.csv_module_list_state[module_name] = csv_module_info

        #with the session state variables, we can now return the lists by saving to the session state variables, we
        #won't need to run the query again

def get_ship_stock_list(ship_names: list):
    if not st.session_state.get('ship_list_state'):
        st.session_state.ship_list_state = {}
    if not st.session_state.get('csv_ship_list_state'):
        st.session_state.csv_ship_list_state = {}

    logger.info(f"Ship names: {ship_names}")
    for ship in ship_names:
        if ship not in st.session_state.ship_list_state:
            logger.info(f"Querying database for {ship}")
            params = {"ship": ship}
            extra = ""
            if ship == "Ferox Navy Issue":
                extra = " AND fit_id = :fit_id"
                params["fit_id"] = 473
            elif ship == "Hurricane Fleet Issue":
                extra = " AND fit_id = :fit_id"
                params["fit_id"] = 494

            query = text(
                f"""
                SELECT type_name, type_id, total_stock, fits_on_mkt, fit_id
                FROM doctrines
                WHERE type_name = :ship{extra}
                LIMIT 1
                """
            )
            df = read_df(mkt_db, query, params)
            if not df.empty and pd.notna(df.loc[0, 'total_stock']) and pd.notna(df.loc[0, 'type_id']) and pd.notna(df.loc[0, 'fits_on_mkt']):
                ship_id = int(df.loc[0, 'type_id'])
                ship_stock = int(df.loc[0, 'total_stock'])
                ship_fits = int(df.loc[0, 'fits_on_mkt'])
                ship_target = get_ship_target(ship_id, 0)
                ship_info = f"{ship} (Qty: {ship_stock} | Fits: {ship_fits} | Target: {ship_target})"
                csv_ship_info = f"{ship},{ship_id},{ship_stock},{ship_fits},{ship_target}\n"
            else:
                ship_info = ship
                csv_ship_info = f"{ship},0,0,0,0\n"

            st.session_state.ship_list_state[ship] = ship_info
            st.session_state.csv_ship_list_state[ship] = csv_ship_info

@st.fragment
def fitting_download_button():
    data = get_all_fit_data()
    _, summary_data = create_fit_df()
    targets = summary_data[['fit_id', 'ship_target']]
    data = data.merge(targets, on='fit_id', how='left')
    data = data.reset_index(drop=True)

    if st.download_button("Download Data", data=data.to_csv(index=False), file_name="wc_doctrine_fits.csv", help="Download all doctrine fit information as a CSV file", mime="text/csv"):
        st.toast("Data downloaded successfully", icon="✅")

def get_ship_target(ship_id: int, fit_id: int) -> int:
    """Get the target for a given ship id or fit id
    if searching by ship_id, enter zero for fit_id
    if searching by fit_id, enter zero for ship_id
    """
    if ship_id == 0 and fit_id == 0:
        logger.error("Error: Both ship_id and fit_id are zero")
        st.error("Error: Both ship_id and fit_id are zero")
        return 20

    elif ship_id == 0:
        try:
            df = read_df(mkt_db, text("SELECT ship_target FROM ship_targets WHERE fit_id = :fit_id"), {"fit_id": fit_id})
            if not df.empty and pd.notna(df.loc[0, 'ship_target']):
                return int(df.loc[0, 'ship_target'])
            return 20
        except Exception as e:
            logger.error(f"Error getting target for fit_id: {fit_id}")
            logger.error(f"Error: {e}")
            st.sidebar.error(f"Did not find a target for fit_id: {fit_id}, we'll just use 20 as default")
            return 20
    else:
        try:
            df = read_df(mkt_db, text("SELECT ship_target FROM ship_targets WHERE ship_id = :ship_id"), {"ship_id": ship_id})
            if not df.empty and pd.notna(df.loc[0, 'ship_target']):
                return int(df.loc[0, 'ship_target'])
            return 20
        except Exception as e:
            logger.error(f"Error getting target for ship_id: {ship_id}, using 20 as default")
            logger.error(f"Error: {e}")
            st.sidebar.error(f"Did not find a target for ship_id: {ship_id}, we'll just use 20 as default")
            return 20

def get_tgt_from_fit_summary(fit_summary: pd.DataFrame, fit_id: int) -> int:
    """Get the target for a given fit id from the fit summary"""
    return fit_summary[fit_summary['fit_id'] == fit_id]['target'].iloc[0]

def main():
    # Handle clearing of checkbox states if requested
    # This must happen BEFORE any widgets are created
    if 'selected_ships' not in st.session_state:
        st.session_state.selected_ships = []
    if 'selected_modules' not in st.session_state:
        st.session_state.selected_modules = []
    if 'ship_list_state' not in st.session_state:
        st.session_state.ship_list_state = {}
    if 'csv_ship_list_state' not in st.session_state:
        st.session_state.csv_ship_list_state = {}
    if 'module_list_state' not in st.session_state:
        st.session_state.module_list_state = {}
    if 'csv_module_list_state' not in st.session_state:
        st.session_state.csv_module_list_state = {}

    if st.session_state.get('clear_ship_checkboxes', False):
        # Delete all ship checkbox keys that match the pattern
        keys_to_delete = [k for k in st.session_state.keys() if isinstance(k, str) and k.startswith('ship_') 
                        and k not in ['selected_ships', 'ship_list_state', 'csv_ship_list_state']]
        for key in keys_to_delete:
            st.session_state[key] = False
        st.session_state.clear_ship_checkboxes = False

    if st.session_state.get('clear_module_checkboxes', False):
        # Delete all module checkbox keys (they don't start with 'ship_' and are numeric pattern)
        keys_to_delete = [k for k in st.session_state.keys()
                         if isinstance(k, str) and '_' in k and not k.startswith('ship_')
                         and k not in ['selected_modules', 'module_list_state', 'csv_module_list_state',
                                      'selected_ships', 'ship_list_state', 'csv_ship_list_state',
                                      'displayed_ships', 'ds_target_multiplier', 'clear_ship_checkboxes',
                                      'clear_module_checkboxes']]
        for key in keys_to_delete:
            st.session_state[key] = False
        st.session_state.clear_module_checkboxes = False

    # App title and logo
    col1, col2, col3 = st.columns([0.2, 0.5, 0.3])
    with col1:
        image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"
        if image_path.exists():
            st.image(str(image_path), width=150)

        else:
            st.warning("Logo image not found")

    with col2:
        st.markdown("&nbsp;")
        st.title("Doctrine Status")
    with col3:
        try:
            fit_summary = get_fit_summary()
            st.markdown("&nbsp;")
            st.markdown("&nbsp;")
            fitting_download_button()
            st.markdown("<span style='font-size: 12px; color: #666;'>*Download all doctrine fit data*</span>", unsafe_allow_html=True)

        except Exception as e:
            logger.error(f"Error getting fit summary: {e}")
            st.warning("No doctrine fits found in the database.")
            return

    # Add filters in the sidebar
    st.sidebar.header("Filters")

    # Target multiplier
    ds_target_multiplier = 1.0
    if 'ds_target_multiplier' not in st.session_state:
        st.session_state.ds_target_multiplier = ds_target_multiplier
    with st.sidebar.expander("Target Multiplier"):
        ds_target_multiplier = st.slider("Target Multiplier", min_value=0.5, max_value=2.0, value=1.0, step=0.1)
        st.session_state.ds_target_multiplier = ds_target_multiplier
        st.sidebar.write(f"Target Multiplier: {ds_target_multiplier}")

    # Status filter
    status_options = ["All", "Critical", "Needs Attention", "All Low Stock", "Good"]
    selected_status = st.sidebar.selectbox("Doctrine Status:", status_options)

    # Ship group filter
    ship_groups = ["All"] + sorted(fit_summary["ship_group"].unique().tolist())
    selected_group = st.sidebar.selectbox("Ship Group:", ship_groups)

    # Get unique ship names for selection
    unique_ships = sorted(fit_summary["ship_name"].unique().tolist())

    # Initialize session state for ship selection if not exists
    if 'selected_ships' not in st.session_state:
        st.session_state.selected_ships = []

    # Initialize session state for ship display (showing all ships)
    if 'displayed_ships' not in st.session_state:
        st.session_state.displayed_ships = unique_ships.copy()

    # Module status filter
    st.sidebar.subheader("Module Filters")
    module_status_options = ["All", "Critical", "Needs Attention", "All Low Stock", "Good"]
    selected_module_status = st.sidebar.selectbox("Module Status:", module_status_options)

    # Apply filters
    filtered_df = fit_summary.copy()
    filtered_df['target'] = filtered_df['target'] * ds_target_multiplier

    # Apply status filter
    if selected_status != "All":
        if selected_status == "Good":
            filtered_df = filtered_df[filtered_df['target_percentage'] > 90]
        elif selected_status == "All Low Stock":
            filtered_df = filtered_df[filtered_df['target_percentage'] <= 90]
        elif selected_status == "Needs Attention":
            filtered_df = filtered_df[(filtered_df['target_percentage'] > 40) & (filtered_df['target_percentage'] <= 90)]
        elif selected_status == "Critical":
            filtered_df = filtered_df[filtered_df['target_percentage'] <= 40]

    # Apply ship group filter
    if selected_group != "All":
        filtered_df = filtered_df[filtered_df['ship_group'] == selected_group]
    
    st.sidebar.checkbox("Show low stock hulls only", value=False, key="show_low_stock_hulls_only")
    if st.session_state.get('show_low_stock_hulls_only', False):
        filtered_df = filtered_df[filtered_df['hulls'] <= filtered_df['target'] * 0.9]

    # Update the displayed ships based on filters
    st.session_state.displayed_ships = filtered_df['ship_name'].unique().tolist()

    if filtered_df.empty:
        st.info("No fits found with the selected filters.")
        return

    # Initialize module selection for export
    if 'selected_modules' not in st.session_state:
        st.session_state.selected_modules = []

    # Group the data by ship_group
    grouped_fits = filtered_df.groupby('ship_group')

    # Iterate through each group and display fits
    for group_name, group_data in grouped_fits:
        # Display group header
        st.subheader(body=f"{group_name}", help="Ship doctrine group", divider="orange")

        # Display the fits in this group
        for i, row in group_data.iterrows():
            # Create a more compact horizontal section for each fit
            col1, col2, col3 = st.columns([1, 3, 2])

            target_pct = row['target_percentage']
            target = int(row['target']) if pd.notna(row['target']) else 0
            fits = int(row['fits']) if pd.notna(row['fits']) else 0
            hulls = int(row['hulls']) if pd.notna(row['hulls']) else 0

            with col1:
                # Ship image and ID info
                try:
                    st.image(f"https://images.evetech.net/types/{row['ship_id']}/render?size=64", width=64)
                except Exception:
                    st.text("Image not available")

                if target_pct > 90:
                    color = "green"
                    status = "Good"
                elif target_pct > 40:
                    color = "orange"
                    status = "Needs Attention"
                else:
                    color = "red"
                    status = "Critical"

                st.badge(status, color=color)
                st.text(f"ID: {row['fit_id']}")
                st.text(f"Fit: {row['fit']}")

            with col2:
                # Ship name with checkbox and metrics in a more compact layout
                ship_cols = st.columns([0.05, 0.95])

                with ship_cols[0]:
                    # Add checkbox next to ship name with unique key using fit_id and ship_name
                    unique_key = f"ship_{row['fit_id']}_{row['ship_name']}"

                    if row['ship_name'] in st.session_state.selected_ships:
                        st.session_state[unique_key] = True

                    st.checkbox("x", key=unique_key,
                                value=st.session_state.get(unique_key, False), label_visibility="hidden")
                    if st.session_state.get(unique_key, False) == True and row['ship_name'] not in st.session_state.selected_ships:
                        st.session_state.selected_ships.append(row['ship_name'])
                        logger.info(f"Added {row['ship_name']} to selected ships")
                    elif st.session_state.get(unique_key, False) == True and row['ship_name'] in st.session_state.selected_ships:
                        logger.info(f"Ship {row['ship_name']} already in selected ships")

                with ship_cols[1]:
                    st.markdown(f"### {row['ship_name']}")

                # Display metrics in a single row
                metric_cols = st.columns(3)
                fits_delta = fits-target
                hulls_delta = hulls-target

                with metric_cols[0]:
                    # Format the delta values
                    if fits:
                        st.metric(label="Fits", value=f"{int(fits)}", delta=fits_delta)
                    else:
                        st.metric(label="Fits", value="0", delta=fits_delta)

                with metric_cols[1]:
                    if hulls:
                        st.metric(label="Hulls", value=f"{int(hulls)}", delta=hulls_delta)
                    else:
                        st.metric(label="Hulls", value="0", delta=hulls_delta)

                with metric_cols[2]:
                    if target:
                        st.metric(label="Target", value=f"{int(target)}")
                    else:
                        st.metric(label="Target", value="0")

                # Progress bar for target percentage
                target_pct = row['target_percentage']
                color = "green" if target_pct >= 90 else "orange" if target_pct >= 50 else "red"
                if target_pct == 0:
                    color2 = "#5c1f06"
                else:
                    color2 = "#333"

                st.markdown(
                    f"""
                    <div style="margin-top: 5px;">
                        <div style="background-color: {color2}; width: 100%; height: 20px; border-radius: 3px;">
                            <div style="background-color: {color}; width: {target_pct}%; height: 20px; border-radius: 3px; text-align: center; line-height: 20px; color: white; font-weight: bold;">
                                {target_pct}%
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with col3:
                # Low stock modules with selection checkboxes
                st.markdown(":blue[**Low Stock Modules:**]")
                for i, module in enumerate(row['lowest_modules']):
                    module_qty = module.split("(")[1].split(")")[0]
                    module_name = module.split(" (")[0]
                    # Make each key unique by adding fit_id and index to avoid duplicates
                    module_key = f"{row['fit_id']}_{i}_{module_name}_{module_qty}"
                    display_key = f"{module_name}"

                    # Determine module status
                    if int(module_qty) <= row['target'] * 0.2:
                        module_status = "Critical"
                    elif int(module_qty) <= row['target']:
                        module_status = "Needs Attention"
                    else:
                        module_status = "Good"

                    # Apply module status filter
                    if selected_module_status == "All Low Stock":
                        if int(module_qty) <= row['target'] * 0.9:
                            module_status = "All Low Stock"
                    if selected_module_status != "All" and selected_module_status != module_status:
                        continue

                    col_a, col_b = st.columns([0.1, 0.9])
                    with col_a:

                        if display_key in st.session_state.selected_modules:
                            st.session_state[module_key] = True

                        st.checkbox("1", key=module_key, label_visibility="hidden",
                                        value=st.session_state.get(module_key, False))
                        if st.session_state.get(module_key, False) == True and display_key not in st.session_state.selected_modules:
                            logger.info(f"Adding {display_key}-{module_key} to selected modules")
                            st.session_state.selected_modules.append(display_key)
                        elif st.session_state.get(module_key, False) == True and display_key in st.session_state.selected_modules:
                            logger.info(f"Module {display_key}-{module_key} already in selected modules")


                    with col_b:
                        if int(module_qty) <= row['target'] * 0.2:
                            st.markdown(f":red-badge[:material/error: {module}]")
                        elif int(module_qty) <= row['target']:
                            st.markdown(f":orange-badge[:material/error: {module}]")
                        else:
                            st.text(module)

            # Add a thinner divider between fits
            st.markdown("<hr style='margin: 0.5em 0; border-width: 1px'>", unsafe_allow_html=True)

        # Add divider between groups
        # st.markdown("<hr style='margin: 1.5em 0; border-width: 2px'>", unsafe_allow_html=True)

    # Ship and Module Export Section
    st.sidebar.markdown("---")
    st.sidebar.header("🔄 Export")

    # Ship selection
    st.sidebar.subheader("Ship Selection")
    ship_col1, ship_col2 = st.sidebar.columns(2)

    # Add "Select All Ships" button
    if ship_col1.button("📋 Select All Ships", width='content', help="select all ships that are currently visible based on filters"):
        st.session_state.selected_ships = st.session_state.displayed_ships.copy()
        st.rerun()

    # Add "Clear Ship Selection" button
    if ship_col2.button("🗑️ Clear Ships", width='content', help="clear all selected ships"):
        st.session_state.selected_ships = []
        st.session_state.ship_list_state = {}
        st.session_state.csv_ship_list_state = {}
        st.session_state.clear_ship_checkboxes = True

        logger.info("Cleared ship selection and session state")
        logger.info(f"Session state ship list: {st.session_state.ship_list_state}")
        logger.info(f"Session state csv ship list: {st.session_state.csv_ship_list_state}")
        logger.info(f"\n{"-"*60}\n")
        st.rerun()

    # Module selection
    st.sidebar.subheader("Module Selection")
    col1, col2 = st.sidebar.columns(2)

    # Add "Select All Modules" functionality
    if col1.button("📋 Select All Modules", width='content', help="select all modules that are currently visible based on filters"):
        # Create a list to collect all module keys that are currently visible based on filters
        visible_modules = []
        low_stock_modules = []
        selected_module_keys = []
        for _, group_data in grouped_fits:
            for _, row in group_data.iterrows():
                # Only include ships that are displayed (match filters)
                if row['ship_name'] not in st.session_state.displayed_ships:
                    continue

                for module in row['lowest_modules']:
                    module_qty = module.split("(")[1].split(")")[0]
                    module_name = module.split(" (")[0]
                    display_key = f"{module_name}"

                    # Determine module status for filtering
                    if selected_module_status == "All Low Stock":
                        if int(module_qty) <= row['target'] * 0.9:
                            low_stock_modules.append(display_key)
                    elif int(module_qty) <= row['target'] * 0.2:
                        module_status = "Critical"
                    elif int(module_qty) <= row['target']:
                        module_status = "Needs Attention"
                    else:
                        module_status = "Good"

                    # Apply module status filter
                    if selected_module_status != "All" and selected_module_status != module_status:
                        continue

                    logger.info(f"Module status: {module_status}")
                    logger.info(f"Module qty: {display_key}")

                    visible_modules.append(display_key)

        # Update session state with all visible modules
        if selected_module_status == "All Low Stock":
            st.session_state.selected_modules = list(set(low_stock_modules))
        else:
            st.session_state.selected_modules = list(set(visible_modules))
        st.rerun()

    # Clear module selection button
    if col2.button("🗑️ Clear Modules", width='content', help="clear all selected modules"):
        st.session_state.selected_modules = []
        st.session_state.module_list_state = {}
        st.session_state.csv_module_list_state = {}
        st.session_state.clear_module_checkboxes = True

        logger.info("Cleared module selection and session state")
        logger.info(f"Session state module list: {st.session_state.module_list_state}")
        logger.info(f"Session state csv module list: {st.session_state.csv_module_list_state}")
        logger.info(f"\n{"-"*60}\n")
        st.rerun()

    # Display selected ships if any
    if st.session_state.selected_ships:
        logger.info(f"Selected ships: {st.session_state.selected_ships}")
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Selected Ships:")
        num_selected_ships = len(st.session_state.selected_ships)
        logger.info(f"Number of selected ships: {num_selected_ships}")
        ship_container_height = 100 if num_selected_ships <= 2 else num_selected_ships * 50

        # Create a scrollable container for selected ships
        with st.sidebar.container(height=ship_container_height):
            get_ship_stock_list(st.session_state.selected_ships)
            logger.info(f"Ship list state: {st.session_state.ship_list_state}")
            ship_list = [st.session_state.ship_list_state[ship] for ship in st.session_state.ship_list_state.keys()]
            csv_ship_list = [st.session_state.csv_ship_list_state[ship] for ship in st.session_state.csv_ship_list_state.keys()]
            for ship in ship_list:
                st.text(ship)
    # Display selected modules if any
    if st.session_state.selected_modules:
        # Get module names
        module_names = list(set(st.session_state.selected_modules))

        # Query market stock (total_stock) for these modules
        get_module_stock_list(module_names)

        st.sidebar.markdown("---")
        st.sidebar.markdown("### Selected Modules:")
        num_selected_modules = len(st.session_state.selected_modules)
        module_container_height =  100 if num_selected_modules <= 2 else num_selected_modules * 50


        module_list = [st.session_state.module_list_state[module] for module in module_names]
        csv_module_list = [st.session_state.csv_module_list_state[module] for module in module_names]

        # Create a scrollable container for selected modules
        with st.sidebar.container(height=module_container_height):
            for module in module_list:
                st.text(module)

    # Show export options if anything is selected
    if st.session_state.selected_ships or st.session_state.selected_modules:
        st.sidebar.markdown("---")

        # Export options in columns
        col1, col2 = st.sidebar.columns(2)

        # Prepare export text
        export_text = ""
        csv_export = ""

        if st.session_state.selected_ships:
            export_text += "SHIPS:\n" + "\n".join(ship_list)
            csv_export += "Type,TypeID,Quantity,Fits,Target\n"  # Updated CSV header
            csv_export += "".join(csv_ship_list)

            if st.session_state.selected_modules:
                export_text += "\n\n"

        if st.session_state.selected_modules:
            # Get module names
            module_names = list(set(st.session_state.selected_modules))

            export_text += "MODULES:\n" + "\n".join(module_list)

            if not st.session_state.selected_ships:
                csv_export += "Type,TypeID,Quantity,Fits,Target\n"
            csv_export += "".join(csv_module_list)

        # Download button
        col1.download_button(
            label="📥 Download CSV",
            data=csv_export,
            file_name="doctrine_export.csv",
            mime="text/csv",
            width='content'
        )
        # Copy to clipboard button
        if col2.button("📋 Copy to Clipboard", width='content'):
            st.sidebar.code(export_text, language="")
            st.sidebar.success("Copied to clipboard! Use Ctrl+C to copy the text above.")
    else:
        st.sidebar.info("Select ships and modules to export by checking the boxes next to them.")

     # Display last update timestamp
    st.sidebar.markdown("---")
    st.sidebar.write(f"Last ESI update: {get_update_time()}")

if __name__ == "__main__":
    main()
