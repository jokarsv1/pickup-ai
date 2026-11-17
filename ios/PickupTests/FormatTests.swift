import XCTest
@testable import Pickup

final class FormatTests: XCTestCase {
    func testPhoneNumbers() {
        XCTAssertEqual(Format.phone("+919876543210"), "+91 98765 43210")
        XCTAssertEqual(Format.phone("+912226543210"), "+91 22 2654 3210")
        XCTAssertEqual(Format.phone("+14155552671"), "+14155552671")
        XCTAssertEqual(Format.phone(nil), "")
    }

    func testIndianMobileInput() {
        XCTAssertEqual(Format.indianMobile("98765 43210"), "+919876543210")
        XCTAssertEqual(Format.indianMobile("09876543210"), "+919876543210")
        XCTAssertEqual(Format.indianMobile("+91 98765-43210"), "+919876543210")
        XCTAssertNil(Format.indianMobile("12345"))
    }

    func testTimesWithAndWithoutZone() {
        XCTAssertNotNil(Format.date("2026-11-17T09:00:00+05:30"))
        XCTAssertNotNil(Format.date("2026-11-17T04:28:00.123456Z"))
        XCTAssertEqual(Format.date("2026-11-17T04:28:00Z"), Format.date("2026-11-17T04:28:00"))  // no zone means UTC
    }

    func testDayLabels() {
        let now = Date()
        XCTAssertEqual(Format.dayLabel(ISO8601DateFormatter().string(from: now), now: now), "Today")
        XCTAssertEqual(Format.dayLabel(ISO8601DateFormatter().string(from: now.addingTimeInterval(-86_400)), now: now), "Yesterday")
    }

    func testDurations() {
        XCTAssertEqual(Format.duration(65), "1m 5s")
        XCTAssertEqual(Format.duration(41), "41s")
        XCTAssertEqual(Format.duration(nil), "")
    }
}
