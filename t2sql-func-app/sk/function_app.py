from services.semantic_service import SemanticService
import azure.functions as func
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
semantic_service = SemanticService()


@app.route(route="api/t2sql")
def semantic(req: func.HttpRequest) -> func.HttpResponse:
    input_text = req.params.get('input')
    if not input_text:
        return func.HttpResponse("Please provide input text.", status_code=400)
    result = semantic_service.process(input_text)
    return func.HttpResponse(result, status_code=200)
