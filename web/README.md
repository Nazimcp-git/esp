# Sign Language Glove — Cloud Layer & Web Platform

This folder contains the Firebase Hosting reader website and Firestore security rules.

## Overview
- **Public Reader**: Visitors can read approved spoken phrases in real time, filter by category (`Emergency`, `Daily needs`), search, and listen to speech output via the Web Speech API.
- **Admin Review Queue**: Authenticated administrators can review raw signs queued with `private` status, approving or rejecting them before they become public.
- **Firestore Security Rules**: Strict access control ensuring unauthenticated visitors can ONLY query `approved` records, wearer can create `private` records, and only authenticated admins can change statuses.

## Deployment Instructions

### 1. Prerequisites
Install the Firebase CLI and log in:
```bash
npm install -g firebase-tools
firebase login
```

### 2. Configure Firebase Project
Link this folder to your Firebase project:
```bash
firebase use --add
# Select your project (e.g. sign-glove)
```

Update your Firebase credentials in `public/app.js`:
```javascript
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  // ...
};
```

### 3. Deploy Firestore Rules and Indexes
```bash
firebase deploy --only firestore
```

### 4. Deploy Hosting
```bash
firebase deploy --only hosting
```

### 5. Local Development / Emulation
You can test the website and Firestore rules locally without deploying:
```bash
firebase emulators:start
```
Or simply open `public/index.html` in any web browser to run in interactive Demo Mode.

