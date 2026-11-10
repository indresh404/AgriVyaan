import 'package:flutter_test/flutter_test.dart';
import 'package:app/models/models.dart';

DroneScan createScan({
  DateTime? createdAt,
  DroneScanStatus status = DroneScanStatus.requested,
}) {
  return DroneScan(
    id: 'booking-id',
    fieldId: 'field-id',
    createdAt: createdAt,
    scanType: 'Crop Health Scan',
    date: '2026-11-10',
    time: '10:00 AM',
    operatorName: 'Pending Assignment',
    status: status,
    verificationStatus: 'PENDING',
  );
}

void main() {
  group('Drone booking cancellation window', () {
    final bookedAt = DateTime.utc(2026, 11, 10, 8);

    test('allows cancellation before eight hours have elapsed', () {
      expect(
        createScan(createdAt: bookedAt)
            .canCancelAt(bookedAt.add(const Duration(hours: 7, minutes: 59))),
        isTrue,
      );
    });

    test('does not allow cancellation at or after eight hours', () {
      final scan = createScan(createdAt: bookedAt);

      expect(scan.canCancelAt(bookedAt.add(const Duration(hours: 8))), isFalse);
      expect(scan.canCancelAt(bookedAt.add(const Duration(hours: 9))), isFalse);
    });

    test('does not allow cancellation when booking time is missing or in the future', () {
      expect(createScan().canCancelAt(bookedAt), isFalse);
      expect(
        createScan(createdAt: bookedAt.add(const Duration(minutes: 1)))
            .canCancelAt(bookedAt),
        isFalse,
      );
    });

    test('does not allow cancellation once the scan has started', () {
      expect(
        createScan(
          createdAt: bookedAt,
          status: DroneScanStatus.inProgress,
        ).canCancelAt(bookedAt.add(const Duration(hours: 1))),
        isFalse,
      );
    });
  });
}
