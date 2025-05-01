import os
import io

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive'
]


def _authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    docs_service = build('docs', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    return docs_service, drive_service


def _copy_doc(drive_service, original_doc_id, new_title="Temporary Copy"):
    copied_file = {
        'name': new_title,
        'mimeType': 'application/vnd.google-apps.document'
    }
    copied = drive_service.files().copy(fileId=original_doc_id, body=copied_file).execute()
    return copied['id']


def _delete_doc(drive_service, doc_id):
    drive_service.files().delete(fileId=doc_id).execute()
    print(f"Deleted temporary document (ID: {doc_id})")


def _replace_text(doc_id, docs_service, replacements: dict):
    requests_list = []
    for old_text, new_text in replacements.items():
        requests_list.append({
            'replaceAllText': {
                'containsText': {
                    'text': old_text,
                    'matchCase': True
                },
                'replaceText': new_text
            }
        })

    if requests_list:
        docs_service.documents().batchUpdate(
            documentId=doc_id, body={'requests': requests_list}).execute()

    print(f"Replaced {len(replacements)} terms in document.")


def _download_pdf(doc_id, drive_service, output_file):
    request = drive_service.files().export_media(fileId=doc_id, mimeType='application/pdf')
    fh = io.FileIO(output_file, 'wb')
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%.")

    print(f"Document downloaded as {output_file}.")


def update_and_download_pdf(doc_id, replacements, output_name='output', save=False) -> None:
    """
    Updates and downloads a Google Docs document as PDF after replacing specified text

    Args:
        doc_id (str): The ID of the original Google Docs document to be updated.
        replacements (dict): A dictionary where keys are text and values are the replacement text.
        output_name (str, optional): The name of the output PDF file (without extension).
        save (bool, optional): If True, a temporary document will be saved.

    Returns:
        None
    """
    with open('credentials.json', 'r') as file:
        if file.read() == '':
            raise ValueError("credentials.json is empty. Please provide valid credentials.")

    docs_service, drive_service = _authenticate()
    tid = _copy_doc(drive_service, doc_id)
    _replace_text(tid, docs_service, replacements)
    _download_pdf(tid, drive_service, output_name + '.pdf')

    if not save:
        _delete_doc(drive_service, tid)
