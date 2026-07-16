"""
BrickView: Real Estate Analytics Platform
Streamlit Dashboard

Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# =========================================================
# 0. PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="BrickView - Real Estate Analytics",
    page_icon="🏠",
    layout="wide"
)

# =========================================================
# 1. DATABASE CONNECTION
# =========================================================
# ⚠️ Apna password/host yahan change karein agar zarurat ho
DB_USER = "root"
DB_PASSWORD = "123456789"
DB_HOST = "localhost"
DB_NAME = "Project"

@st.cache_resource
def get_engine():
    engine = create_engine(
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    )
    return engine

engine = get_engine()

@st.cache_data(ttl=60)
def load_table(table_name):
    return pd.read_sql(f"SELECT * FROM {table_name}", engine)

def run_query(query):
    return pd.read_sql(query, engine)

def refresh_cache():
    st.cache_data.clear()

# =========================================================
# 2. LOAD BASE TABLES
# =========================================================
df_listings = load_table("listings")
df_property = load_table("property")
df_agents = load_table("agents")
df_sales = load_table("sales")
df_buyers = load_table("buyers")

# NOTE: Column names apke actual schema ke hisaab se adjust karein
# (upar diye gaye code me kahin capital, kahin small letters mixed hain)

# =========================================================
# 3. SIDEBAR NAVIGATION
# =========================================================
st.sidebar.title("🏠 BrickView")
page = st.sidebar.radio(
    "Navigate",
    ["📊 Filters & Overview", "📈 Visualizations", "🛠 CRUD Operations", "🧮 SQL Queries"]
)

# =========================================================
# 4. PAGE 1: FILTERS & OVERVIEW
# =========================================================
if page == "📊 Filters & Overview":
    st.title("📊 Filters & Overview")

    col1, col2, col3 = st.columns(3)

    with col1:
        cities = sorted(df_listings["City"].dropna().unique())
        selected_cities = st.multiselect("City", cities, default=cities)

    with col2:
        types = sorted(df_listings["Property_Type"].dropna().unique())
        selected_types = st.multiselect("Property Type", types, default=types)

    with col3:
        agents_list = sorted(df_agents["Name"].dropna().unique())
        selected_agent = st.selectbox("Agent (search)", ["All"] + agents_list)

    min_price, max_price = int(df_listings["Price"].min()), int(df_listings["Price"].max())
    price_range = st.slider("Price Range", min_price, max_price, (min_price, max_price))

    date_col = "Listed_Date" if "Listed_Date" in df_listings.columns else None
    if date_col:
        df_listings[date_col] = pd.to_datetime(df_listings[date_col])
        min_date, max_date = df_listings[date_col].min(), df_listings[date_col].max()
        date_range = st.date_input("Listed Date Range", (min_date, max_date))

    # Apply filters
    filtered = df_listings[
        df_listings["City"].isin(selected_cities) &
        df_listings["Property_Type"].isin(selected_types) &
        df_listings["Price"].between(price_range[0], price_range[1])
    ]

    if selected_agent != "All":
        agent_id = df_agents.loc[df_agents["Name"] == selected_agent, "Agent_ID"].values
        if len(agent_id) > 0:
            filtered = filtered[filtered["Agent_ID"] == agent_id[0]]

    if date_col and len(date_range) == 2:
        filtered = filtered[
            (filtered[date_col] >= pd.to_datetime(date_range[0])) &
            (filtered[date_col] <= pd.to_datetime(date_range[1]))
        ]

    st.markdown(f"### Showing {len(filtered)} listings")
    st.dataframe(filtered, use_container_width=True)

    # Quick KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Listings", len(filtered))
    k2.metric("Avg Price", f"₹{filtered['Price'].mean():,.0f}" if len(filtered) else "N/A")
    k3.metric("Cities", filtered["City"].nunique())
    k4.metric("Property Types", filtered["Property_Type"].nunique())

    # store filtered data for use in visualization page
    st.session_state["filtered_listings"] = filtered

# =========================================================
# 5. PAGE 2: VISUALIZATIONS
# =========================================================
elif page == "📈 Visualizations":
    st.title("📈 Visualizations")

    data = st.session_state.get("filtered_listings", df_listings)

    # ---- Map ----
    st.subheader("🗺️ Property Locations")
    if "Latitude" in data.columns and "Longitude" in data.columns:
        map_df = data.rename(columns={"Latitude": "lat", "Longitude": "lon"})
        st.map(map_df[["lat", "lon"]].dropna())
    else:
        st.info("Latitude/Longitude columns not found in listings table.")

    col1, col2 = st.columns(2)

    # ---- Bar Chart: Avg price by city ----
    with col1:
        st.subheader("📊 Average Price by City")
        avg_price_city = (
            data.groupby("City")["Price"].mean().round(2).sort_values(ascending=False)
        )
        st.bar_chart(avg_price_city)

    # ---- Pie Chart: Property type distribution ----
    with col2:
        st.subheader("🥧 Property Type Distribution")
        type_counts = data["Property_Type"].value_counts()
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.pie(type_counts.values, labels=type_counts.index, autopct="%1.1f%%")
        ax.axis("equal")
        st.pyplot(fig)

    # ---- Line Chart: Monthly sales trend ----
    st.subheader("📈 Monthly Sales Trend")
    if "Sale_Date" in df_sales.columns:
        sales_copy = df_sales.copy()
        sales_copy["Sale_Date"] = pd.to_datetime(sales_copy["Sale_Date"])
        sales_copy["Month"] = sales_copy["Sale_Date"].dt.to_period("M").astype(str)
        monthly_trend = sales_copy.groupby("Month").size()
        st.line_chart(monthly_trend)
    else:
        st.info("Sale_Date column not found in sales table.")

    # ---- Table View with pagination ----
    st.subheader("📋 Table View")
    page_size = st.selectbox("Rows per page", [10, 25, 50, 100], index=1)
    total_rows = len(data)
    total_pages = max(1, (total_rows - 1) // page_size + 1)
    page_num = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    start = (page_num - 1) * page_size
    end = start + page_size
    st.dataframe(data.iloc[start:end], use_container_width=True)

# =========================================================
# 6. PAGE 3: CRUD OPERATIONS
# =========================================================
elif page == "🛠 CRUD Operations":
    st.title("🛠 CRUD Operations")

    table_map = {
        "listings": df_listings,
        "property": df_property,
        "agents": df_agents,
        "sales": df_sales,
        "buyers": df_buyers
    }

    table_choice = st.selectbox("Select Table", list(table_map.keys()))
    df_current = load_table(table_choice)  # always fresh

    tab_view, tab_add, tab_update, tab_delete = st.tabs(
        ["👁 View", "➕ Add", "✏️ Update", "🗑 Delete"]
    )

    # ---- VIEW ----
    with tab_view:
        st.dataframe(df_current, use_container_width=True)

    # ---- ADD ----
    with tab_add:
        st.write(f"Add a new record to **{table_choice}**")
        new_row = {}
        with st.form(f"add_form_{table_choice}"):
            for col in df_current.columns:
                new_row[col] = st.text_input(col, key=f"add_{table_choice}_{col}")
            submitted = st.form_submit_button("Add Record")

        if submitted:
            try:
                cols = ", ".join(new_row.keys())
                placeholders = ", ".join([f":{c}" for c in new_row.keys()])
                query = text(f"INSERT INTO {table_choice} ({cols}) VALUES ({placeholders})")
                with engine.begin() as conn:
                    conn.execute(query, new_row)
                st.success("Record added successfully!")
                refresh_cache()
            except Exception as e:
                st.error(f"Error: {e}")

    # ---- UPDATE ----
    with tab_update:
        st.write(f"Update a record in **{table_choice}**")
        id_col = df_current.columns[0]  # assume first column is primary key
        record_id = st.selectbox(f"Select {id_col}", df_current[id_col].unique())
        record = df_current[df_current[id_col] == record_id].iloc[0]

        with st.form(f"update_form_{table_choice}"):
            updated_values = {}
            for col in df_current.columns:
                updated_values[col] = st.text_input(
                    col, value=str(record[col]), key=f"upd_{table_choice}_{col}"
                )
            update_submit = st.form_submit_button("Update Record")

        if update_submit:
            try:
                set_clause = ", ".join([f"{c} = :{c}" for c in updated_values.keys() if c != id_col])
                updated_values["record_id_value"] = record_id
                query = text(
                    f"UPDATE {table_choice} SET {set_clause} WHERE {id_col} = :record_id_value"
                )
                with engine.begin() as conn:
                    conn.execute(query, updated_values)
                st.success("Record updated successfully!")
                refresh_cache()
            except Exception as e:
                st.error(f"Error: {e}")

    # ---- DELETE ----
    with tab_delete:
        st.write(f"Delete a record from **{table_choice}**")
        id_col = df_current.columns[0]
        del_id = st.selectbox(f"Select {id_col} to delete", df_current[id_col].unique(), key="del_select")

        if st.button("Delete Record", type="primary"):
            try:
                query = text(f"DELETE FROM {table_choice} WHERE {id_col} = :del_id")
                with engine.begin() as conn:
                    conn.execute(query, {"del_id": del_id})
                st.success("Record deleted successfully!")
                refresh_cache()
            except Exception as e:
                st.error(f"Error: {e}")

# =========================================================
# 7. PAGE 4: SQL QUERIES DISPLAY
# =========================================================
elif page == "🧮 SQL Queries":
    st.title("🧮 SQL Queries & Insights")

    queries = {
        "1. Average listing price by city": """
            SELECT City, ROUND(AVG(Price), 2) AS Average_Listing_Price
            FROM listings GROUP BY City ORDER BY Average_Listing_Price DESC;
        """,
        "2. Average price per sqft by property type": """
            SELECT Property_Type, ROUND(AVG(Price / Area_sqft), 2) AS Avg_Price_Per_Sqft
            FROM listings GROUP BY Property_Type ORDER BY Avg_Price_Per_Sqft DESC;
        """,
        "3. Furnishing status vs average price": """
            SELECT p.Furnishing_Status, ROUND(AVG(l.Price), 2) AS Avg_Price
            FROM property p
            JOIN listings l ON p.Listing_ID = l.Listing_ID
            GROUP BY p.Furnishing_Status;
        """,
        "9. Highest average price by city": """
            SELECT City, ROUND(AVG(Price), 2) AS Avg_Price
            FROM listings GROUP BY City ORDER BY Avg_Price DESC;
        """,
        "11. Average days on market by city": """
            SELECT l.City, ROUND(AVG(s.Days_On_Market), 2) AS Avg_Days_On_Market
            FROM listings l
            JOIN sales s ON l.Listing_ID = s.Listing_ID
            GROUP BY l.City ORDER BY Avg_Days_On_Market;
        """,
        "19. Agents with most sales": """
            SELECT a.Name, COUNT(*) AS Total_Sales
            FROM sales s
            JOIN listings l ON s.Listing_ID = l.Listing_ID
            JOIN agents a ON l.Agent_ID = a.Agent_ID
            GROUP BY a.Name ORDER BY Total_Sales DESC;
        """,
        "26. Buyer type distribution": """
            SELECT Buyer_Type, COUNT(*) AS Count
            FROM buyers GROUP BY Buyer_Type;
        """,
        # 👉 Apne baaki saare queries yahan is pattern me add kar sakte hain
    }

    for label, query in queries.items():
        with st.expander(label):
            st.code(query, language="sql")
            try:
                result = run_query(query)
                st.dataframe(result, use_container_width=True)
            except Exception as e:
                st.error(f"Error running query: {e}")
