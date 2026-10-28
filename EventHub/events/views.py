from django.db import transaction
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Event, Reservation
from .serializers import EventSerializer, ReservationSerializer


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer

    def get_queryset(self):
        queryset     = Event.objects.all()
        if self.action in ('update', 'partial_update'):
            queryset = queryset.select_for_update()
        status_param = self.request.query_params.get('status')
        venue_param  = self.request.query_params.get('venue')
        if status_param:
            queryset = queryset.filter(status=status_param)
        if venue_param:
            queryset = queryset.filter(venue__icontains=venue_param)
        return queryset

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            return super().update(request, *args, **kwargs)


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer

    def get_queryset(self):
        queryset = Reservation.objects.all()
        if self.action in ('cancel', 'destroy', 'update', 'partial_update'):
            queryset = queryset.select_for_update()
        event_id = self.request.query_params.get('event_id')
        if event_id:
            if not (event_id.isascii() and event_id.isdigit()) or int(event_id) < 1:
                raise serializers.ValidationError({'event_id': ['Must be a positive integer.']})
            queryset = queryset.filter(event_id=int(event_id))
        return queryset

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.status == 'confirmed':
            event = Event.objects.select_for_update().get(pk=instance.event_id)
            event.available_seats += instance.seats_reserved
            event.save(update_fields=['available_seats'])
        instance.delete()

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        with transaction.atomic():
            reservation = self.get_object()
            if reservation.status == 'cancelled':
                return Response({'error': 'Already cancelled.'}, status=400)
            event = Event.objects.select_for_update().get(pk=reservation.event_id)
            event.available_seats += reservation.seats_reserved
            event.save(update_fields=['available_seats'])
            reservation.status = 'cancelled'
            reservation.save(update_fields=['status'])
        return Response(self.get_serializer(reservation).data)
