import csv
from django.core.management.base import BaseCommand
from core.models import Station

# Strict whitelist of US State codes to filter out Canadian provinces (AB, BC, ON, etc.)
US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
}

class Command(BaseCommand):
    help = 'Imports OPIS Truckstop data, filters USA only, and deduplicates by Rack ID'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the OPIS CSV file')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        
        raw_stations = []
        skipped_count = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    state = row.get('State', '').strip().upper()
                    if state not in US_STATES:
                        skipped_count += 1
                        continue # Drop Canadian provinces
                    
                    price_str = row.get('Retail Price', '').strip()
                    if not price_str:
                        raise ValueError("Missing price")
                    price = float(price_str)
                    
                    raw_stations.append({
                        'opis_id': int(row['OPIS Truckstop ID']),
                        'name': row['Truckstop Name'].strip(),
                        'address': row['Address'].strip(),
                        'city': row['City'].strip(),
                        'state': state,
                        'rack_id': int(row['Rack ID']),
                        'retail_price': price,
                    })
                except (ValueError, TypeError, KeyError) as e:
                    self.stdout.write(self.style.WARNING(f"Skipping malformed row: {row.get('OPIS Truckstop ID', 'Unknown')}"))
                    skipped_count += 1
                    continue
        
        self.stdout.write(f"Found {len(raw_stations)} USA stations before deduplication. Skipped {skipped_count} rows.")
        
        # Deduplicate by Rack ID (keep the lowest retail price for the physical location)
        deduped = {}
        for s in raw_stations:
            rack = s['rack_id']
            if rack not in deduped or s['retail_price'] < deduped[rack]['retail_price']:
                deduped[rack] = s
                
        self.stdout.write(f"Deduplicated to {len(deduped)} unique physical locations.")
        
        # Clear existing data to ensure idempotency on re-runs
        Station.objects.all().delete()
        
        # Bulk create for performance
        stations_to_create = [
            Station(
                opis_id=s['opis_id'],
                name=s['name'],
                address=s['address'],
                city=s['city'],
                state=s['state'],
                rack_id=s['rack_id'],
                retail_price=s['retail_price'],
                latitude=None, # Populated in Phase 3 Geocoding step
                longitude=None
            )
            for s in deduped.values()
        ]
        
        Station.objects.bulk_create(stations_to_create, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f"Successfully imported {len(stations_to_create)} stations into SQLite."))