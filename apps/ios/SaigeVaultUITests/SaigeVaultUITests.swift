import XCTest

final class SaigeVaultUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        app = XCUIApplication()
        // Disables App Lock so the tests can reach the UI.
        app.launchArguments = ["-ui-testing"]
        app.launch()
    }

    @MainActor
    func testTabsAreReachable() {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 10))
        for (tab, title) in [("Files", "Files"), ("Search", "Search"), ("Ask Saige", "Ask Saige"), ("Settings", "Settings")] {
            tabBar.buttons[tab].tap()
            XCTAssertTrue(app.navigationBars[title].waitForExistence(timeout: 5), "\(title) did not appear")
        }
    }

    @MainActor
    func testQuickActionExplainsUnavailableFeature() {
        app.buttons["Scan document"].firstMatch.tap()
        let alert = app.alerts.firstMatch
        XCTAssertTrue(alert.waitForExistence(timeout: 5))
        XCTAssertTrue(alert.label.contains("Document scanner"))
        alert.buttons["OK"].tap()
    }
}
