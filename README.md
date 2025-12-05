## Getting Started

These instructions will help you set up and run the EHR System on your local machine.

### Prerequisites

* **Python 3.10+** installed
* Required Python packages (install via pip):

```bash
pip install -r requirements.txt
```

The `requirements.txt` should include at minimum:

```
customtkinter
opencv-python
Pillow
PyPDF2
```
### Running the Application

1. **Clone or download the repository**

```bash
git clone <repository_url>
cd Multimodal_EHR_System
```

2. **Launch the application**

```bash
python app.py
```

3. **Login or Register**

* **Login:** Use your credentials to access your dashboard.
* **Register:** Create a new account using facial recognition and/or fingerprint verification.

---

## Using the Dashboards

### User Dashboard

* **View EHR:** Access your latest electronic health records.
* **Update EHR:** Manually update personal medical history or upload structured JSON files.
* **Download Records:** Download your records for personal use.
* **View Blockchain Logs:** See all system actions related to your account for transparency.

### Admin Dashboard

* **Manage Users:** Create, edit, or delete users.
* **Upload EHR:** Add patient EHR files with automatic validation.
* **Download EHR:** Download individual or all user records.
* **Blockchain Audit:** View tamper-proof logs of all actions performed in the system.
* **PDF Extraction:** Extract structured data from uploaded PDF documents.

---

## Notes

* **Data Security:** All records are stored securely in `data/ehr_files` with tamper-evident blockchain logging.
* **Biometric Data:** Stored locally for authentication purposes. Facial images and fingerprint templates are not shared externally.
* **File Formats:** JSON is the preferred format for structured EHR upload. PDF extraction is supported for text-based reports.

