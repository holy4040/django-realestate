from codecs import lookup_error
from dataclasses import field
import logging
import django

import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles import serializers

from .exceptions import PropertyNotFound
from .models import Property, PropertyViews
from .pagination import PropertyPagination
from .serializers import (PropertyCreateSerializer,PropertySerializer,PropertyViewSerializer)

logger = logging.getLogger(__name__)

class PropertyFilter(django_filters.FilterSet):
    advert_type = django_filters.CharFilter(
        field_name="advert_type", lookup_expr="iexact"
    )
    property_type = django_filters.CharFilter(
        field_name="property_type", lookup_expr="iexact"
    )
    price = django_filters.NumberFilter()
    price_gt = django_filters.NumberFilter(
        field_name="price", lookup_expr="gt"
    )
    price_lt = django_filters.NumberFilter(
        field_name="price", lookup_expr="lt"
    )

    class Meta:
        model = Property
        fields = ["advert_type", "property_type", "price"]

class ListAllPropertiesAPIView(generics.ListAPIView):
    serializer_class = PropertySerializer
    queryset = Property.objects.all().order_by("-created_at")
    pagination_class = PropertyPagination
    filter_backends = [
        DjangoFilterBackend, 
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = PropertyFilter
    search_fields = ["country","city"]
    ordering_fields = ["created_at"]


class ListAgentsPropertiesAPIView(generics.ListAPIView):
    serializer_class = PropertySerializer
    pagination_class = PropertyPagination
    filter_backends = [
        DjangoFilterBackend, 
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = PropertyFilter
    search_fields = ["country","city"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = Property.objects.filter(user=user).order_by("-created_at")
        return queryset

class PropertyViewsAPIView(generics.ListAPIView):
    serializer_class = PropertyViewSerializer
    queryset = PropertyViews.objects.all()

class PropertyDetailView(APIView):
    def get(self, request, slug):
        property = Property.objects.get(slug=slug)
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        
        if not PropertyViews.objects.filter(property=property,ip=ip).exists():
            PropertyViews.objects.create(property=property,ip=ip)
            property.views += 1
            property.save()
        
        serializers = PropertySerializer(property, context={"request":request})
        return Response(serializers.data, status=status.HTTP_200_OK)

@api_view(["PUT"])
@permission_classes([permissions.IsAuthenticated])
def update_property_api_view(request, slug):
    try:
        property = Property.objects.get(slug=slug)
    except Property.DoesNotExist:
        raise PropertyNotFound
    user = request.user
    if property.user != user:
        return Response(
            {"error": "You can't update or edit a property that doesn't belong to you"},status=status.HTTP_403_FORBIDDEN,
        )
    if request.method == "PUT":
        data = request.data
        serializers = PropertySerializer(property, data, many=False)
        serializers.is_valid(raise_exception=True)
        serializers.save()
        return Response(serializers.data)

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def create_property_api_view(request):
    user = request.user
    data = request.data
    serializers = PropertyCreateSerializer(data=data)
    if serializers.is_valid():
        serializers.save()
        logger.info(
            f"property {serializers.data.get('title')} created by {user.username}"
        )
        return Response(serializers.data)
    return Response(serializers.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def delete_property_api_view(request, slug):
    try:
        property = Property.objects.get(slug=slug)
    except Property.DoesNotExist:
        raise PropertyNotFound
    user = request.user
    if property.user != user:
        return Response(
            {"error": "You can't delete a property that doesn't belong to you"},status=status.HTTP_403_FORBIDDEN,
        )
    if request.method == "DELETE":
        delete_operation = property.delete()
        data = {}
        if delete_operation:
            data["success"] = "Deletion was successful"
        else:
            data["failure"] = "Deletion failed"
        return Response(data=data)

@api_view(["POST"])
def uploadPropertyImage(request):
    data = request.data
    property_id = data["property_id"]
    property = Property.objects.get(id=property_id)
    property.cover_photo = request.FILES.get("cover_photo")
    property.photo1 = request.FILES.get("photo1")
    property.photo2 = request.FILES.get("photo2")
    property.photo3 = request.FILES.get("photo3")
    property.photo4 = request.FILES.get("photo4")
    property.save()
    return Response("Image(s) uploaded")

class PropertySearchAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    serializers_class = PropertyCreateSerializer
    
    def post(self, request):
        queryset = Property.objects.filter(published_status=True)
        data = self.request.data
        advert_type = data['advert_type']
        queryset = queryset.filter(advert_type__iexact=advert_type)

        property_type = data['property_type']
        queryset = queryset.filter(property_type__iexact=property_type)

        price = data['price']
        priceset = {
            "$0+":0,
            "$50,000+":50000,
            "$100,000+":100000,
            "$200,000+":200000,
            "$400,000+":400000,
            "$600,000+":600000,
            "Any":-1
        }
        if price != -1:
            queryset = queryset.filter(price__gte=priceset[price])
        
        bedrooms = data["bedrooms"]
        bedroomset = {
            "0+":0,
            "1+":1,
            "2+":2,
            "3+":3,
            "4+":4,
            "5+":5
        }
        queryset = queryset.filter(bedrooms__gte=bedroomset[bedrooms])

        bathrooms = data["bathrooms"]
        bathroomset = {
            "0+":0.0,
            "1+":1.0,
            "2+":2.0,
            "3+":3.0,
            "4+":4.0
        }
        queryset = queryset.filter(bathrooms__gte=bathroomset[bathrooms])

        catch_phrase = data["catch_phrase"]
        queryset = queryset.filter(description__icontains=catch_phrase)

        serializers = PropertySerializer(queryset, many=True)

        return Response(serializers.data)