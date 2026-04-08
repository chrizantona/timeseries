import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json

# Configuration
API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Система Автоматического Вызова Транспорта",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Красивый дизайн
st.markdown("""
<style>
    /* Основной фон */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Карточки */
    .css-1r6slb0 {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }
    
    /* Метрики */
    .big-metric {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
    }
    
    /* Приоритеты */
    .priority-critical {
        background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        box-shadow: 0 4px 15px rgba(255, 65, 108, 0.4);
    }
    .priority-high {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        box-shadow: 0 4px 15px rgba(245, 87, 108, 0.4);
    }
    .priority-normal {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
        box-shadow: 0 4px 15px rgba(79, 172, 254, 0.4);
    }
    
    /* Заголовки */
    h1 {
        color: white !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        font-size: 3rem !important;
    }
    
    h2, h3 {
        color: #667eea !important;
    }
    
    /* Кнопки */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 12px 30px;
        font-weight: bold;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
    
    /* Sidebar */
    .css-1d391kg {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
    }
    
    /* Таблицы */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* Инпуты */
    .stNumberInput>div>div>input {
        border-radius: 10px;
        border: 2px solid #667eea;
    }
    
    /* Успех/Ошибка */
    .stSuccess {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        border-radius: 10px;
        color: white;
    }
    
    .stError {
        background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
        border-radius: 10px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Title with animation
st.markdown("""
<div style='text-align: center; padding: 20px;'>
    <h1>🚛 Система Автоматического Вызова Транспорта</h1>
    <p style='color: white; font-size: 1.2rem; text-shadow: 1px 1px 2px rgba(0,0,0,0.3);'>
        Умное планирование отгрузок с использованием AI
    </p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Настройки")
    
    vehicle_capacity = st.number_input(
        "Vehicle Capacity",
        min_value=1,
        max_value=20,
        value=5,
        help="Вместимость одной машины"
    )
    
    already_ordered = st.number_input(
        "Already Ordered",
        min_value=0,
        max_value=50,
        value=0,
        help="Уже вызвано машин"
    )
    
    use_dynamic_safety = st.checkbox(
        "Dynamic Safety Factor",
        value=True,
        help="Автоматический расчет запаса"
    )
    
    manual_safety = None
    if not use_dynamic_safety:
        manual_safety = st.slider(
            "Manual Safety",
            min_value=1.0,
            max_value=1.5,
            value=1.1,
            step=0.05
        )
    
    st.markdown("---")
    st.markdown("### 🎯 Features")
    st.markdown("""
    - ✅ Dynamic safety
    - ✅ Smart priority
    - ✅ Explainable AI
    - ✅ One-click plan
    - ✅ Real-time monitor
    """)
    
    st.markdown("---")
    st.markdown("### 📊 System Status")
    try:
        health = requests.get(f"{API_URL}/health", timeout=2).json()
        if health["status"] == "ok":
            st.success("🟢 Online")
        else:
            st.warning("🟡 Degraded")
    except:
        st.error("🔴 Offline")

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Планирование",
    "📈 Monitoring",
    "📋 Orders",
    "🔍 What-If"
])

# Tab 1: Dispatch Planning
with tab1:
    st.markdown("## 🎯 Создать План")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📥 Input Data")
        
        col_id1, col_id2 = st.columns(2)
        with col_id1:
            route_id = st.number_input("Route ID", min_value=1, value=105)
        with col_id2:
            office_id = st.number_input("Office ID", min_value=1, value=42)
        
        col_date, col_time = st.columns(2)
        with col_date:
            timestamp = st.date_input("Дата", value=datetime.now())
        with col_time:
            time = st.time_input("Время", value=datetime.now().time())
        full_timestamp = datetime.combine(timestamp, time)
        
        st.markdown("### 📦 Status Pipeline")
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            status_1 = st.number_input("Status 1", 0, 100, 18, key="s1")
            status_2 = st.number_input("Status 2", 0, 100, 11, key="s2")
        with col_s2:
            status_3 = st.number_input("Status 3", 0, 100, 9, key="s3")
            status_4 = st.number_input("Status 4", 0, 100, 6, key="s4")
        with col_s3:
            status_5 = st.number_input("Status 5", 0, 100, 5, key="s5")
            status_6 = st.number_input("Status 6", 0, 100, 4, key="s6")
        with col_s4:
            status_7 = st.number_input("Status 7", 0, 100, 3, key="s7")
            status_8 = st.number_input("Status 8", 0, 100, 2, key="s8")
        
        # Visualize pipeline
        pipeline_data = {
            'Stage': ['Early', 'Mid', 'Late'],
            'Items': [
                status_1 + status_2,
                status_3 + status_4 + status_5,
                status_6 + status_7 + status_8
            ]
        }
        fig_pipeline = px.bar(
            pipeline_data,
            x='Stage',
            y='Items',
            title='Pipeline Distribution',
            color='Items',
            color_continuous_scale='Purples'
        )
        fig_pipeline.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=14)
        )
        st.plotly_chart(fig_pipeline, use_container_width=True)
    
    with col2:
        st.subheader("Dispatch Plan")
        
        if st.button("🚀 Generate Plan", type="primary", use_container_width=True):
            with st.spinner("Calculating optimal dispatch plan..."):
                try:
                    # Call API
                    payload = {
                        "route_id": route_id,
                        "office_from_id": office_id,
                        "timestamp": full_timestamp.isoformat(),
                        "status_1": status_1,
                        "status_2": status_2,
                        "status_3": status_3,
                        "status_4": status_4,
                        "status_5": status_5,
                        "status_6": status_6,
                        "status_7": status_7,
                        "status_8": status_8,
                        "vehicle_capacity": vehicle_capacity,
                        "already_ordered": already_ordered,
                        "safety_factor": manual_safety
                    }
                    
                    response = requests.post(
                        f"{API_URL}/plan/dispatch",
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Display results
                        st.success("✅ Plan generated successfully!")
                        
                        # Key metrics
                        metric_col1, metric_col2, metric_col3 = st.columns(3)
                        with metric_col1:
                            st.metric(
                                "Forecast (2h)",
                                f"{result['forecast_2h']:.1f}",
                                help="Predicted shipment volume"
                            )
                        with metric_col2:
                            st.metric(
                                "Vehicles Needed",
                                result['additional_vehicles'],
                                help="Additional vehicles to dispatch"
                            )
                        with metric_col3:
                            priority_color = {
                                "critical": "🔴",
                                "high": "🟠",
                                "normal": "🟢",
                                "low": "⚪"
                            }
                            st.metric(
                                "Priority",
                                f"{priority_color.get(result['priority'], '⚪')} {result['priority'].upper()}"
                            )
                        
                        # Details
                        st.markdown("---")
                        st.markdown("**📊 Plan Details**")
                        
                        detail_col1, detail_col2 = st.columns(2)
                        with detail_col1:
                            st.info(f"**Confidence:** {result['confidence']:.1%}")
                            st.info(f"**Safety Factor:** {result['safety_factor_used']:.3f}")
                            st.info(f"**Total Vehicles:** {result['required_vehicles']}")
                        
                        with detail_col2:
                            dispatch_time = datetime.fromisoformat(result['planned_dispatch_time'])
                            st.info(f"**Dispatch Time:** {dispatch_time.strftime('%H:%M')}")
                            minutes_until = (dispatch_time - full_timestamp).seconds // 60
                            st.info(f"**Time Until Dispatch:** {minutes_until} min")
                        
                        # Explanation
                        st.markdown("---")
                        st.markdown("**🔍 Decision Explanation**")
                        
                        with st.expander("Forecast Reasoning", expanded=True):
                            forecast_exp = result['explanation']['forecast']
                            st.write(f"**Prediction:** {forecast_exp['prediction']:.2f}")
                            st.write("**Key Factors:**")
                            for factor in forecast_exp['key_factors']:
                                st.write(f"- {factor}")
                        
                        with st.expander("Priority Reasoning"):
                            priority_exp = result['explanation']['priority']
                            st.write(f"**Priority Score:** {priority_exp['score']}")
                            st.write("**Factors:**")
                            for factor in priority_exp['factors']:
                                st.write(f"- {factor}")
                        
                        # Create order button
                        st.markdown("---")
                        if st.button("📝 Create Transport Order", type="secondary", use_container_width=True):
                            order_payload = {
                                "office_from_id": office_id,
                                "route_id": route_id,
                                "vehicles": result['additional_vehicles'],
                                "priority": result['priority'],
                                "planned_dispatch_time": result['planned_dispatch_time'],
                                "forecast_2h": result['forecast_2h']
                            }
                            
                            order_response = requests.post(
                                f"{API_URL}/orders/create",
                                json=order_payload
                            )
                            
                            if order_response.status_code == 200:
                                order_result = order_response.json()
                                st.success(f"✅ Order created: {order_result['order_id']}")
                            else:
                                st.error("Failed to create order")
                    
                    else:
                        st.error(f"API Error: {response.status_code}")
                        st.json(response.json())
                
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# Tab 2: Monitoring
with tab2:
    st.header("Real-time Monitoring")
    
    # Mock data for demo
    st.info("📊 Monitoring dashboard - showing last 24 hours")
    
    # Generate mock time series
    hours = pd.date_range(end=datetime.now(), periods=24, freq='H')
    mock_forecast = [20 + 10 * (i % 12) / 12 + (i % 3) * 5 for i in range(24)]
    mock_actual = [f + (i % 5 - 2) * 3 for i, f in enumerate(mock_forecast)]
    
    df_monitoring = pd.DataFrame({
        'Time': hours,
        'Forecast': mock_forecast,
        'Actual': mock_actual
    })
    
    fig_monitoring = go.Figure()
    fig_monitoring.add_trace(go.Scatter(
        x=df_monitoring['Time'],
        y=df_monitoring['Forecast'],
        name='Forecast',
        line=dict(color='blue', width=2)
    ))
    fig_monitoring.add_trace(go.Scatter(
        x=df_monitoring['Time'],
        y=df_monitoring['Actual'],
        name='Actual',
        line=dict(color='green', width=2, dash='dot')
    ))
    fig_monitoring.update_layout(
        title='Forecast vs Actual (Last 24h)',
        xaxis_title='Time',
        yaxis_title='Shipment Volume',
        hovermode='x unified'
    )
    st.plotly_chart(fig_monitoring, use_container_width=True)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Avg WAPE", "12.3%", "-2.1%")
    with col2:
        st.metric("Relative Bias", "3.2%", "+0.5%")
    with col3:
        st.metric("Orders Today", "47", "+12")
    with col4:
        st.metric("Vehicles Dispatched", "234", "+18")

# Tab 3: Orders History
with tab3:
    st.header("Orders History")
    
    try:
        response = requests.get(f"{API_URL}/orders")
        if response.status_code == 200:
            orders = response.json()
            
            if orders:
                df_orders = pd.DataFrame(orders)
                
                # Display as table
                st.dataframe(
                    df_orders,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Summary stats
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Orders", len(orders))
                with col2:
                    total_vehicles = df_orders['vehicles'].sum()
                    st.metric("Total Vehicles", total_vehicles)
                with col3:
                    priority_counts = df_orders['priority'].value_counts()
                    high_priority = priority_counts.get('high', 0) + priority_counts.get('critical', 0)
                    st.metric("High Priority", high_priority)
            else:
                st.info("No orders yet. Create your first dispatch plan!")
        else:
            st.error("Failed to load orders")
    except Exception as e:
        st.error(f"Error: {str(e)}")

# Tab 4: What-If Analysis
with tab4:
    st.header("What-If Analysis")
    st.markdown("**Explore how different parameters affect dispatch decisions**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Scenario Parameters")
        
        base_forecast = st.slider("Base Forecast", 10.0, 100.0, 30.0, 5.0)
        
        st.markdown("**Vary Parameters:**")
        safety_range = st.slider(
            "Safety Factor Range",
            1.0, 1.5, (1.0, 1.3), 0.05
        )
        capacity_options = st.multiselect(
            "Vehicle Capacities",
            [3, 5, 7, 10],
            default=[5, 7]
        )
    
    with col2:
        st.subheader("Results")
        
        if capacity_options:
            results = []
            for capacity in capacity_options:
                for safety in [safety_range[0], (safety_range[0] + safety_range[1])/2, safety_range[1]]:
                    import math
                    required = math.ceil(base_forecast * safety / capacity)
                    results.append({
                        'Capacity': capacity,
                        'Safety Factor': f"{safety:.2f}",
                        'Vehicles': required,
                        'Utilization': f"{(base_forecast * safety / (required * capacity)):.1%}"
                    })
            
            df_results = pd.DataFrame(results)
            st.dataframe(df_results, use_container_width=True, hide_index=True)
            
            # Visualization
            fig_whatif = px.bar(
                df_results,
                x='Capacity',
                y='Vehicles',
                color='Safety Factor',
                barmode='group',
                title='Vehicles Needed by Capacity and Safety Factor'
            )
            st.plotly_chart(fig_whatif, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    🚛 Transport Dispatch Service v1.0 | Built with FastAPI + Streamlit | 
    <a href='http://localhost:8000/docs' target='_blank'>API Docs</a>
</div>
""", unsafe_allow_html=True)
