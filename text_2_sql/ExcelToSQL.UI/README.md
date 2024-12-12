# Excel to SQL Query UI

This is the frontend interface for the Excel to SQL Query solution, built with ASP.NET Core MVC. It provides a user-friendly interface for uploading Excel files and querying them using natural language.

## Project Structure

```
ExcelToSQL.UI/
├── Views/                     # MVC Views
│   ├── Shared/               # Shared layouts and partials
│   │   └── _Layout.cshtml    # Main layout template
│   ├── Admin/                # Admin views
│   │   └── UploadData.cshtml # File upload interface
│   └── Query/                # Query views
│       └── Index.cshtml      # SQL query chat interface
├── wwwroot/                  # Static files
│   ├── css/
│   │   └── site.css         # Site-wide styles
│   ├── js/
│   │   └── site.js          # Site-wide JavaScript
│   └── images/
│       └── logos/           # Application logos
├── config.json              # Application configuration
└── README.md               # This file
```

## Features

1. Excel File Upload
   - Drag-and-drop interface
   - Support for .xlsx, .xls, and .csv files
   - File validation and progress tracking
   - List of uploaded files with management options

2. Natural Language Query Interface
   - Chat-style interface for querying data
   - Shows generated SQL queries
   - Displays results in formatted tables
   - Support for complex queries and aggregations

## Setup Instructions

1. Prerequisites
   - .NET 6.0 SDK or later
   - Python backend running (for API endpoints)

2. Configuration
   - Update `config.json` with your settings:
     ```json
     {
       "API": {
         "BaseUrl": "http://localhost:5000",  // Your Python backend URL
       },
       "Upload": {
         "StorageConnectionString": ""  // Your storage connection string
       }
     }
     ```

3. Running Locally
   ```bash
   # Install dependencies
   dotnet restore

   # Run the application
   dotnet run
   ```

4. Access the application at `http://localhost:5000`

## Integration with Python Backend

The frontend expects these API endpoints:

1. File Upload API
   ```
   POST /api/upload
   Content-Type: multipart/form-data
   
   Response:
   {
     "id": "file_id",
     "name": "filename.xlsx",
     "uploadDate": "2024-01-01T12:00:00Z"
   }
   ```

2. Query API
   ```
   POST /api/query
   Content-Type: application/json
   {
     "query": "Show me total sales by region"
   }
   
   Response:
   {
     "sql": "SELECT region, SUM(sales) as total_sales FROM ...",
     "results": [...],
     "explanation": "Here's the breakdown of sales by region..."
   }
   ```

3. Files API
   ```
   GET /api/files
   Response:
   [{
     "id": "file_id",
     "name": "filename.xlsx",
     "uploadDate": "2024-01-01T12:00:00Z"
   }]
   ```

## Customization

1. Styling
   - Modify `wwwroot/css/site.css` for custom styling
   - Update theme colors in `config.json`

2. Behavior
   - Adjust file upload settings in `config.json`
   - Modify chat interface behavior in `wwwroot/js/site.js`

3. Layout
   - Customize page layout in `Views/Shared/_Layout.cshtml`
   - Modify component views in respective folders

## Security

1. Authentication
   - Enable authentication in `config.json`
   - Configure Azure AD settings if using Azure AD authentication

2. File Upload Security
   - File type validation
   - Size limits
   - Virus scanning (implement in backend)

3. API Security
   - CORS configuration
   - Rate limiting (implement in backend)
   - Request validation

## Monitoring

1. Application Insights
   - Configure in `config.json`
   - Tracks:
     - Page views
     - API calls
     - Errors
     - User behavior

2. Logging
   - Configure log levels in `config.json`
   - Structured logging for better analysis

## Contributing

1. Code Style
   - Follow existing patterns
   - Use meaningful variable names
   - Add comments for complex logic

2. Testing
   - Test UI components
   - Verify API integration
   - Check responsive design

3. Pull Requests
   - Create feature branches
   - Include documentation updates
   - Add test coverage

## License

This project is licensed under the MIT License - see the LICENSE file for details.
