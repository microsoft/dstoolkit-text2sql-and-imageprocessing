import logging
import os
from azure.ai.vision.imageanalysis.aio import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential


async def process_ocr(record: dict) -> dict:
    logging.info("Python HTTP trigger function processed a request.")

    try:
        url = record["data"]["image"]["url"]
        logging.info(f"Request Body: {record}")
    except KeyError:
        return {
            "recordId": record["recordId"],
            "data": {},
            "errors": [
                {
                    "message": "Failed to extract data with ocr. Pass a valid source in the request body.",
                }
            ],
            "warnings": None,
        }
    else:
        logging.info(f"image url: {url}")

        if url is not None:
            try:
                # keyvault_helper = KeyVaultHelper()
                client = ImageAnalysisClient(
                    endpoint=os.environ["AIService__Services__Endpoint"],
                    credential=AzureKeyCredential(os.environ["AIService__Services__Key"])
                ),
                result = await client.analyze_from_url(
                    image_url=url, visual_features=[VisualFeatures.READ]
                )
                logging.info("logging output")

                # Extract text from OCR results
                text = " ".join([line.text for line in result.read.blocks[0].lines])
                logging.info(text)

            except KeyError as e:
                logging.error(e)
                logging.error(f"Failed to authenticate with ocr: {e}")
                return {
                    "recordId": record["recordId"],
                    "data": {},
                    "errors": [
                        {
                            "message": f"Failed to authenticate with Ocr. Check the service credentials exist. {e}",
                        }
                    ],
                    "warnings": None,
                }
            except Exception as e:
                logging.error(e)
                logging.error(
                    f"Failed to analyze the document with Azure Document Intelligence: {e}"
                )
                logging.error(e.InnerError)
                return {
                    "recordId": record["recordId"],
                    "data": {},
                    "errors": [
                        {
                            "message": f"Failed to analyze the document with ocr. Check the source and try again. {e}",
                        }
                    ],
                    "warnings": None,
                }
        else:
            return {
                "recordId": record["recordId"],
                "data": {"text": ""},
            }

        return {
            "recordId": record["recordId"],
            "data": {"text": text},
        }