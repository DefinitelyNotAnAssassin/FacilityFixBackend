# Inventory Forecasting Feature

## Overview
The Inventory Forecasting feature provides predictive analytics for inventory management, helping administrators anticipate when items will need to be reordered based on historical usage patterns.

## Backend Implementation

### API Endpoint
```
GET /inventory/forecasting/{building_id}
```

**Authentication:** Required (Admin role)
**Response:** Array of forecasting data objects

### Response Format
```json
[
  {
    "id": "item_123",
    "name": "Light Bulb",
    "category": "Electrical",
    "status": "Active",
    "stock": "8/10",
    "usage": "2.5",
    "trend": {
      "icon": "trending_up",
      "color": "green"
    },
    "daysToMin": "150d",
    "reorderBy": "Aug 30"
  }
]
```

### Calculations

#### Monthly Usage
- Analyzes transactions from the last 90 days
- Calculates average daily usage
- Converts to monthly usage rate

#### Trend Analysis
- Compares current month vs previous month usage
- **Trending Up (Green):** >10% increase
- **Trending Down (Red):** >10% decrease
- **Stable (Grey):** ±10% change

#### Days to Minimum
- Time until stock reaches reorder level
- Based on current stock and daily usage rate
- Shows "N/A" if no usage data or already below reorder level

#### Reorder Date
- Estimated date when stock will reach reorder level
- Shows "Immediate" if already below reorder level

## Testing

### Unit Tests
Run the forecasting logic tests:
```bash
python scripts/test_inventory_forecasting_comprehensive.py
```

### API Tests
Test the actual endpoint (requires running server):
```bash
python scripts/test_inventory_forecasting_api.py
```

## Frontend Integration

### Sample Flutter Implementation
```dart
// Add to your state class
List<Map<String, dynamic>> _forecastingData = [];
bool _isLoading = true;

// Fetch data method
Future<void> _fetchForecastingData() async {
  setState(() => _isLoading = true);

  try {
    final buildingId = 'your_building_id';
    final response = await http.get(
      Uri.parse('YOUR_API_BASE_URL/inventory/forecasting/$buildingId'),
      headers: {
        'Authorization': 'Bearer YOUR_JWT_TOKEN',
        'Content-Type': 'application/json',
      },
    );

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      setState(() {
        _forecastingData = List<Map<String, dynamic>>.from(data);
        _isLoading = false;
      });
    }
  } catch (e) {
    setState(() => _isLoading = false);
  }
}

// Icon mapping
IconData _getTrendIcon(String iconName) {
  switch (iconName) {
    case 'trending_up': return Icons.trending_up;
    case 'trending_down': return Icons.trending_down;
    default: return Icons.trending_flat;
  }
}

Color _getTrendColor(String colorName) {
  switch (colorName) {
    case 'green': return Colors.green;
    case 'red': return Colors.red;
    default: return Colors.grey;
  }
}
```

## Database Requirements

### Collections Used
- `inventory`: Item definitions and current stock levels
- `inventory_transactions`: Historical usage data

### Required Fields
- Inventory items need: `current_stock`, `reorder_level`, `max_stock_level`
- Transactions need: `inventory_id`, `transaction_type`, `quantity`, `created_at`

## Configuration

The forecasting uses a 90-day lookback period for usage calculations. This can be adjusted in the service methods if needed.

## Error Handling

- Returns empty array if no inventory items found
- Handles missing transaction data gracefully
- Provides fallback values for calculations with insufficient data