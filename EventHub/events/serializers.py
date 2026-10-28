from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers
from rest_framework.settings import api_settings

from .models import Event, Reservation


class EventSerializer(serializers.ModelSerializer):
    reservations_count = serializers.SerializerMethodField()

    class Meta:
        model  = Event
        fields = ['id', 'title', 'venue', 'date', 'total_seats',
                  'available_seats', 'status', 'created_at', 'reservations_count']

    def get_reservations_count(self, obj):
        return obj.reservations.filter(status='confirmed').count()

    def validate(self, data):
        total_seats     = data.get('total_seats', getattr(self.instance, 'total_seats', 0))
        available_seats = data.get('available_seats', getattr(self.instance, 'available_seats', 0))
        if available_seats > total_seats:
            raise serializers.ValidationError('available_seats cannot exceed total_seats.')

        if self.instance is not None:
            booked = self.instance.reservations.filter(status='confirmed').aggregate(
                total=Sum('seats_reserved')
            )['total'] or 0
            if total_seats < booked:
                raise serializers.ValidationError(
                    f'total_seats cannot be less than the {booked} seat(s) already reserved.'
                )
            if available_seats > total_seats - booked:
                raise serializers.ValidationError(
                    f'available_seats cannot exceed {total_seats - booked} '
                    f'(total_seats minus seats already reserved).'
                )
        return data


class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model            = Reservation
        fields           = ['id', 'event', 'attendee_name', 'attendee_email',
                            'seats_reserved', 'status', 'created_at']
        read_only_fields = ['status', 'created_at']

    def to_internal_value(self, data):
        raw_event = data.get('event') if hasattr(data, 'get') else None
        if raw_event is not None:
            is_int       = isinstance(raw_event, int) and not isinstance(raw_event, bool)
            is_digit_str = isinstance(raw_event, str) and raw_event.isascii() and raw_event.isdigit()
            if not (is_int or is_digit_str) or int(raw_event) < 1:
                raise serializers.ValidationError({'event': ['Must be a positive integer event ID.']})
        return super().to_internal_value(data)

    def validate_seats_reserved(self, value):
        if value < 1:
            raise serializers.ValidationError('Must reserve at least 1 seat.')
        return value

    def validate(self, data):
        if self.instance is not None:
            for field in ('event', 'seats_reserved'):
                if field in data and data[field] != getattr(self.instance, field):
                    raise serializers.ValidationError(
                        {field: 'Cannot be changed after reservation. '
                                'Cancel and create a new reservation instead.'}
                    )
            return data

        event = data.get('event')
        if event.status not in ('upcoming', 'ongoing'):
            raise serializers.ValidationError(
                f'Cannot reserve seats for a {event.status} event.'
            )
        if data.get('seats_reserved', 0) > event.available_seats:
            raise serializers.ValidationError(
                f'Only {event.available_seats} seat(s) available.'
            )
        return data

    def create(self, validated_data):
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=validated_data['event'].pk)
            if event.status not in ('upcoming', 'ongoing'):
                raise serializers.ValidationError({
                    api_settings.NON_FIELD_ERRORS_KEY: [f'Cannot reserve seats for a {event.status} event.']
                })
            if validated_data['seats_reserved'] > event.available_seats:
                raise serializers.ValidationError({
                    api_settings.NON_FIELD_ERRORS_KEY: [f'Only {event.available_seats} seat(s) available.']
                })
            event.available_seats -= validated_data['seats_reserved']
            event.save(update_fields=['available_seats'])
            validated_data['event'] = event
            return Reservation.objects.create(**validated_data)
