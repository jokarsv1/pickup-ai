import XCTest

/// Walks through the app on the simulator and saves screenshots.
/// Run by .github/workflows/ios-screenshots.yml against a local dev server filled by
/// backend/scripts/seed_demo.py. Settings come in through TEST_RUNNER_* variables.
final class ScreenshotTour: XCTestCase {
    private let env = ProcessInfo.processInfo.environment

    override func setUp() {
        continueAfterFailure = false
    }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment["PICKUP_API_BASE_URL"] = env["PICKUP_API_BASE_URL"] ?? "http://localhost:8000"
        app.launchEnvironment["UITEST_RESET"] = "1"
        app.launch()
        return app
    }

    private func shot(_ name: String) {
        sleep(2)
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        if let dir = env["SCREENSHOT_DIR"] {
            try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            try? screenshot.pngRepresentation.write(to: URL(fileURLWithPath: dir).appendingPathComponent("\(name).png"))
        }
    }

    private func wait(_ element: XCUIElement, _ timeout: TimeInterval = 25, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(element.waitForExistence(timeout: timeout), "Missing: \(element)", file: file, line: line)
    }

    private func element(_ app: XCUIApplication, containing text: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", text)).firstMatch
    }

    private func signIn(_ app: XCUIApplication, phone: String, capture: Bool) {
        wait(app.buttons["Get started"])
        if capture { shot("01-welcome") }
        app.buttons["Get started"].tap()
        let phoneField = app.textFields["onboarding.phone"]
        wait(phoneField)
        phoneField.tap()
        phoneField.typeText(phone)
        if capture { shot("02-phone-number") }
        app.buttons["Send code"].tap()
        let codeField = app.textFields["onboarding.code"]
        wait(codeField)
        codeField.tap()
        codeField.typeText("123456") // submits on its own at six digits
    }

    func testOnboarding() {
        let app = launch()
        signIn(app, phone: "9800000001", capture: true)
        let name = app.textFields["onboarding.name"]
        wait(name)
        name.tap()
        name.typeText("Asha Rao")
        shot("03-profile")
        app.buttons["Continue"].tap()
        wait(app.staticTexts["Know who's calling, live"])
        shot("04-notifications")
        app.buttons["Not now"].tap()
        wait(app.staticTexts["Send missed calls to your assistant"], 30)
        shot("05-forwarding-setup")
    }

    func testMainApp() {
        let app = launch()
        signIn(app, phone: "9800000002", capture: false)
        let live = element(app, containing: "Live: Sunita")
        wait(live, 30)
        wait(element(app, containing: "Rohit"))
        shot("10-home-calls")

        live.tap()
        wait(element(app, containing: "confirm Asha's appointment"))
        shot("11-live-call")
        app.navigationBars.buttons.element(boundBy: 0).tap()

        element(app, containing: "Rohit · TalentEdge").tap()
        wait(element(app, containing: "senior product manager"))
        shot("12-call-summary")
        app.navigationBars.buttons.element(boundBy: 0).tap()

        app.swipeUp()
        element(app, containing: "74285").tap()
        wait(element(app, containing: "KYC"))
        shot("13-scam-call")
        app.navigationBars.buttons.element(boundBy: 0).tap()

        app.tabBars.buttons["Ask Pickup"].tap()
        wait(element(app, containing: "remind me at 6"))
        shot("14-ask-pickup-chat")

        app.tabBars.buttons["Settings"].tap()
        wait(app.staticTexts["Instructions"])
        shot("15-settings")
        app.staticTexts["Instructions"].tap()
        wait(element(app, containing: "Ready-made packs"))
        shot("16-instructions")
    }
}
