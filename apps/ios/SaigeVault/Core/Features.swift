import Foundation

/// Feature availability registry — mirrors apps/web/src/lib/features.ts.
/// The UI never pretends a capability exists; unbuilt features show the
/// phase in which they ship.
enum Feature: String, CaseIterable, Sendable {
    case auth, googleDrive, files, upload, scanner, collections, search
    case semanticSearch, askSaige, agent, timeline, sync, export

    var label: String {
        switch self {
        case .auth: "Secure sign-in"
        case .googleDrive: "Google Drive connection"
        case .files: "File management"
        case .upload: "Uploads"
        case .scanner: "Document scanner"
        case .collections: "Collections"
        case .search: "Search"
        case .semanticSearch: "Semantic & hybrid search"
        case .askSaige: "Ask Saige"
        case .agent: "Saige agent"
        case .timeline: "Timeline"
        case .sync: "Drive sync"
        case .export: "Data export"
        }
    }

    var phase: Int {
        switch self {
        case .auth: 3
        case .googleDrive: 4
        case .files, .upload, .collections: 5
        case .scanner: 6
        case .search: 8
        case .semanticSearch: 9
        case .timeline: 10
        case .askSaige: 11
        case .agent: 12
        case .sync: 13
        case .export: 14
        }
    }

    var isAvailable: Bool { false }

    var summary: String {
        switch self {
        case .auth: "Google sign-in with server-side sessions, stored in the Keychain."
        case .googleDrive: "Files stay in your Drive; tokens stay encrypted on the server."
        case .files: "Browse, rename, move, favourite, delete and restore your files."
        case .upload: "Upload with server-side validation. Nothing is uploaded without your confirmation."
        case .scanner: "Multi-page scanning with edge detection, perspective correction and OCR."
        case .collections: "Group files virtually without duplicating them."
        case .search: "Filename, full-text and filtered search across your vault."
        case .semanticSearch: "Meaning-based retrieval powered by vector embeddings."
        case .askSaige: "Ask questions and get cited, source-backed answers."
        case .agent: "Multi-step tasks over your documents, with confirmation for any change."
        case .timeline: "Your documents in time, from extracted or confirmed dates only."
        case .sync: "Detect changes made directly in Google Drive."
        case .export: "Export metadata, collections, tags, summaries and chat history."
        }
    }

    var notice: String { "\(label) arrives in Phase \(phase). \(summary)" }
}
