#!/usr/bin/env python3
"""
Demo script for Transport Dispatch Service
Shows all killer features in action
"""

import requests
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()

API_URL = "http://localhost:8000"


def print_header(text):
    console.print(f"\n[bold cyan]{text}[/bold cyan]")
    console.print("=" * 60)


def demo_health_check():
    print_header("1. Health Check")
    
    response = requests.get(f"{API_URL}/health")
    data = response.json()
    
    status_color = "green" if data["status"] == "ok" else "yellow"
    console.print(f"Status: [{status_color}]{data['status'].upper()}[/{status_color}]")
    console.print(f"Models Loaded: {'✅' if data['models_loaded'] else '❌'}")
    console.print(f"Database Connected: {'✅' if data['database_connected'] else '❌'}")


def demo_forecast():
    print_header("2. Forecast with Explainability")
    
    payload = {
        "route_id": 105,
        "office_from_id": 42,
        "timestamp": datetime.now().isoformat(),
        "status_1": 18,
        "status_2": 11,
        "status_3": 9,
        "status_4": 6,
        "status_5": 5,
        "status_6": 4,
        "status_7": 3,
        "status_8": 2
    }
    
    console.print("\n[yellow]Input:[/yellow]")
    console.print(f"Route: {payload['route_id']}, Office: {payload['office_from_id']}")
    console.print(f"Pipeline: Early={payload['status_1']+payload['status_2']}, "
                  f"Mid={payload['status_3']+payload['status_4']+payload['status_5']}, "
                  f"Late={payload['status_6']+payload['status_7']+payload['status_8']}")
    
    response = requests.post(f"{API_URL}/forecast/predict", json=payload)
    data = response.json()
    
    console.print("\n[green]Forecast Result:[/green]")
    console.print(f"📊 Forecast (2h): [bold]{data['forecast_2h']:.2f}[/bold]")
    console.print(f"🎯 Confidence: [bold]{data['confidence']:.1%}[/bold]")
    console.print(f"📈 Uncertainty: [bold]{data.get('uncertainty', 0):.2f}[/bold]")
    
    if 'explanation' in data and 'key_factors' in data['explanation']:
        console.print("\n[cyan]Why this forecast?[/cyan]")
        for factor in data['explanation']['key_factors']:
            console.print(f"  • {factor}")
    
    return data['forecast_2h'], data['confidence'], data.get('uncertainty', 0.1)


def demo_decision(forecast, confidence, uncertainty):
    print_header("3. Smart Decision with Dynamic Safety Factor")
    
    payload = {
        "route_id": 105,
        "office_from_id": 42,
        "forecast_2h": forecast,
        "vehicle_capacity": 5,
        "already_ordered": 1
    }
    
    console.print("\n[yellow]Input:[/yellow]")
    console.print(f"Forecast: {forecast:.2f}")
    console.print(f"Vehicle Capacity: {payload['vehicle_capacity']}")
    console.print(f"Already Ordered: {payload['already_ordered']}")
    
    response = requests.post(f"{API_URL}/decision/calculate", json=payload)
    data = response.json()
    
    console.print("\n[green]Decision Result:[/green]")
    console.print(f"🚛 Required Vehicles: [bold]{data['required_vehicles']}[/bold]")
    console.print(f"➕ Additional Needed: [bold]{data['additional_vehicles']}[/bold]")
    
    priority_colors = {
        "critical": "red",
        "high": "yellow",
        "normal": "green",
        "low": "blue"
    }
    priority_color = priority_colors.get(data['priority'], "white")
    console.print(f"⚡ Priority: [{priority_color}]{data['priority'].upper()}[/{priority_color}]")
    console.print(f"🛡️ Safety Factor: [bold]{data['safety_factor_used']:.3f}[/bold]")
    
    if 'explanation' in data and 'priority_reasoning' in data['explanation']:
        console.print("\n[cyan]Why this priority?[/cyan]")
        reasoning = data['explanation']['priority_reasoning']
        console.print(f"  Score: {reasoning['score']}")
        for factor in reasoning['factors']:
            console.print(f"  • {factor}")


def demo_full_pipeline():
    print_header("4. One-Click Dispatch Planning (Killer Feature!)")
    
    payload = {
        "route_id": 105,
        "office_from_id": 42,
        "timestamp": datetime.now().isoformat(),
        "status_1": 22,
        "status_2": 15,
        "status_3": 12,
        "status_4": 8,
        "status_5": 7,
        "status_6": 6,
        "status_7": 5,
        "status_8": 4,
        "vehicle_capacity": 5,
        "already_ordered": 0
    }
    
    console.print("\n[yellow]Complete Pipeline: Forecast → Decision → Dispatch[/yellow]")
    
    response = requests.post(f"{API_URL}/plan/dispatch", json=payload)
    data = response.json()
    
    # Create results table
    table = Table(title="Dispatch Plan", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Forecast (2h)", f"{data['forecast_2h']:.2f}")
    table.add_row("Confidence", f"{data['confidence']:.1%}")
    table.add_row("Required Vehicles", str(data['required_vehicles']))
    table.add_row("Additional Vehicles", str(data['additional_vehicles']))
    table.add_row("Priority", data['priority'].upper())
    table.add_row("Safety Factor", f"{data['safety_factor_used']:.3f}")
    table.add_row("Dispatch Time", data['planned_dispatch_time'])
    
    console.print(table)
    
    return data


def demo_create_order(plan_data):
    print_header("5. Create Transport Order")
    
    payload = {
        "office_from_id": 42,
        "route_id": 105,
        "vehicles": plan_data['additional_vehicles'],
        "priority": plan_data['priority'],
        "planned_dispatch_time": plan_data['planned_dispatch_time'],
        "forecast_2h": plan_data['forecast_2h']
    }
    
    response = requests.post(f"{API_URL}/orders/create", json=payload)
    data = response.json()
    
    console.print(f"\n[green]✅ Order Created![/green]")
    console.print(f"Order ID: [bold]{data['order_id']}[/bold]")
    console.print(f"Status: {data['status']}")
    console.print(f"Vehicles: {data['vehicles']}")
    console.print(f"Priority: {data['priority']}")


def demo_list_orders():
    print_header("6. View Orders History")
    
    response = requests.get(f"{API_URL}/orders")
    orders = response.json()
    
    if orders:
        table = Table(title=f"Recent Orders ({len(orders)} total)", show_header=True)
        table.add_column("Order ID", style="cyan")
        table.add_column("Route", style="yellow")
        table.add_column("Vehicles", style="green")
        table.add_column("Priority", style="magenta")
        table.add_column("Status", style="blue")
        
        for order in orders[:5]:  # Show last 5
            table.add_row(
                order['order_id'],
                str(order['route_id']),
                str(order['vehicles']),
                order['priority'],
                order['status']
            )
        
        console.print(table)
    else:
        console.print("[yellow]No orders yet[/yellow]")


def main():
    console.print(Panel.fit(
        "[bold cyan]🚛 Transport Dispatch Service Demo[/bold cyan]\n"
        "[yellow]Showcasing all killer features[/yellow]",
        border_style="cyan"
    ))
    
    try:
        # 1. Health check
        demo_health_check()
        
        # 2. Forecast with explainability
        forecast, confidence, uncertainty = demo_forecast()
        
        # 3. Decision with dynamic safety factor
        demo_decision(forecast, confidence, uncertainty)
        
        # 4. Full pipeline
        plan_data = demo_full_pipeline()
        
        # 5. Create order
        demo_create_order(plan_data)
        
        # 6. List orders
        demo_list_orders()
        
        console.print("\n[bold green]✅ Demo completed successfully![/bold green]")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  • Open dashboard: http://localhost:8501")
        console.print("  • View API docs: http://localhost:8000/docs")
        console.print("  • Run tests: pytest tests/")
        
    except requests.exceptions.ConnectionError:
        console.print("\n[bold red]❌ Error: Cannot connect to API[/bold red]")
        console.print("Make sure the service is running:")
        console.print("  docker-compose up")
        console.print("  or")
        console.print("  uvicorn src.api.app:app --reload")
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]")


if __name__ == "__main__":
    main()
