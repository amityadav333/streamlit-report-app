import streamlit as st
import pyodbc
import pandas as pd
import plotly.express as px
import time  # For detecting double-clicks

# Set page layout
st.set_page_config(layout="wide")

# Load company logo
logo_path = "Logo.jpg"

# Function to connect to User's SQL Server (Windows Authentication)
def get_user_db_connection():
    try:
        conn = pyodbc.connect(
            "DRIVER={SQL Server};"
            "SERVER=DESKTOP-RMQIJDO\\SQLEXPRESS;"  
            "DATABASE=SalesDB;"  
            "Trusted_Connection=yes;"
        )
        return conn
    except Exception as e:
        st.error(f"❌ User SQL Server Connection Error: {e}")
        return None

# Function to connect to Boss's SQL Server (SQL Authentication)
def get_boss_db_connection():
    try:
        conn = pyodbc.connect(
            "DRIVER={SQL Server};"
            "SERVER=192.168.27.3;"  
            "DATABASE=AutoNAV;"  
            "UID=sa;"  
            "PWD=kulwant@123;"  
        )
        return conn
    except Exception as e:
        st.error(f"❌ Boss SQL Server Connection Error: {e}")
        return None

# Fetch hierarchical data from Report_Master
@st.cache_data(ttl=0)
def fetch_tree_data():
    query = "SELECT R_ID, Report_Name, R_ID_M FROM dbo.Report_Master"
    conn = get_user_db_connection()
    if conn:
        try:
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"❌ Query Execution Error: {e}")
            return None
    return None

# Function to fetch report query from Report_Master table
def fetch_report_query(R_id):
    query = f"SELECT Query FROM dbo.Report_Master WHERE R_ID = {R_id}"
    conn = get_user_db_connection()
    if conn:
        try:
            df = pd.read_sql(query, conn)
            conn.close()
            if not df.empty:
                return df["Query"].iloc[0]
        except Exception as e:
            st.error(f"❌ Query Fetching Error: {e}")
            return None
    return None

# Function to fetch report data from Boss's SQL Server
def fetch_report_data(query):
    conn = get_boss_db_connection()
    if conn:
        try:
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"❌ Report Query Execution Error: {e}")
            return None
    return None

# Convert SQL table data into tree format
def build_tree(df, parent_id=0):
    tree = []
    children = df[df["R_ID_M"] == parent_id]
    for _, row in children.iterrows():
        node = {
            "label": row["Report_Name"],
            "value": row["R_ID"],
            "children": build_tree(df, row["R_ID"])
        }
        tree.append(node)
    return tree

# Fetch tree data
df_tree = fetch_tree_data()
tree_data = build_tree(df_tree) if df_tree is not None and not df_tree.empty else []

# Initialize session state
if "open_reports" not in st.session_state:
    st.session_state.open_reports = set()
if "selected_report" not in st.session_state:
    st.session_state.selected_report = None
if "selected_query" not in st.session_state:
    st.session_state.selected_query = None
if "execute_report" not in st.session_state:
    st.session_state.execute_report = False
if "click_timestamps" not in st.session_state:
    st.session_state.click_timestamps = {}

# Function to handle single-click and double-click
def handle_click(report_id):
    current_time = time.time()
    
    # Check if this report was clicked recently (double-click detection)
    if report_id in st.session_state.click_timestamps:
        last_click_time = st.session_state.click_timestamps[report_id]
        if current_time - last_click_time < 0.5:  # Double-click detected
            if report_id in st.session_state.open_reports:
                st.session_state.open_reports.remove(report_id)  # Collapse
            else:
                st.session_state.open_reports.add(report_id)  # Expand
        else:
            st.session_state.open_reports.add(report_id)  # Single-click to open
    else:
        st.session_state.open_reports.add(report_id)  # First-time click
    
    # Update last click timestamp
    st.session_state.click_timestamps[report_id] = current_time
    
    # Set selected report and query
    st.session_state.selected_report = report_id
    st.session_state.selected_query = fetch_report_query(report_id)
    st.session_state.execute_report = False  # Reset execution state

# Function to display collapsible tree menu
def display_tree(items, indent=0):
    for item in items:
        spaces = "&nbsp;" * (indent * 4)
        item_key = f"Report_{item['value']}"

        # Check if report is open
        is_open = item["value"] in st.session_state.open_reports

        # Button for report selection
        clicked = st.button(f"{spaces}📂 {item['label']}", key=item_key)

        if clicked:
            handle_click(item["value"])

        # Show children if open
        if "children" in item and is_open:
            display_tree(item["children"], indent=indent+1)

# Layout: Left (Tree) - Right (Reports)
col1, col2 = st.columns([1, 3])

# LEFT COLUMN: Tree structure
with col1:
    st.image(logo_path, width=150)
    st.markdown("<h2>Reports Menu</h2>", unsafe_allow_html=True)
    
    if tree_data:
        display_tree(tree_data)
    else:
        st.warning("⚠️ No tree structure found in the database.")

    # "Select" Button
    if st.session_state.selected_report:
        if st.button("✅ Select Report"):
            st.session_state.execute_report = True

# RIGHT COLUMN: Display reports
with col2:
    st.markdown("<h1 style='text-align: center;'>Welcome UFI FILTERS</h1>", unsafe_allow_html=True)
    tabs = st.tabs(["Report View", "Custom Query"])

    with tabs[0]:
        if st.session_state.execute_report:
            selected_query = st.session_state.selected_query
            if selected_query:
                df = fetch_report_data(selected_query)
                if df is not None and not df.empty:
                    st.dataframe(df)
                    chart_options = ["Bar Chart", "Line Chart", "Pie Chart", "Scatter Plot", "Histogram", "Box Plot"]
                    chart_type = st.selectbox("📈 Select Chart Type", chart_options)
                    x_col = st.selectbox("📊 Select X-Axis Column", df.columns)
                    y_col = st.selectbox("📊 Select Y-Axis Column (Numeric)", df.select_dtypes(include=['number']).columns)
                    fig = px.histogram(df, x=x_col, y=y_col) if chart_type == "Histogram" else px.scatter(df, x=x_col, y=y_col) if chart_type == "Scatter Plot" else px.box(df, x=x_col, y=y_col) if chart_type == "Box Plot" else None
                    if fig:
                            st.plotly_chart(fig)


    with tabs[1]:
        custom_query = st.text_area("Enter your SQL Query:", "SELECT * FROM ReportData;")
        if st.button("🔄 Fetch Data"):
            custom_df = fetch_report_data(custom_query)
            if custom_df is not None and not custom_df.empty:
                st.dataframe(custom_df)
            else:
                st.warning("⚠️ No data found for the custom query.")

                
