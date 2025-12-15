from codecarbon import EmissionsTracker

tracker = EmissionsTracker()
tracker.start()

# โค้ดของคุณ


emissions = tracker.stop()
print(f"CO2 Emissions: {emissions} kg")