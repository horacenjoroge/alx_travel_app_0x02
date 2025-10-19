# ALX Travel App 0x02 - Payment Integration

A Django-based travel booking application with integrated payment processing using the Chapa Payment Gateway.

## Project Overview

This project extends the ALX Travel App by implementing secure payment functionality. Users can browse travel listings, create bookings, and complete payments through the Chapa API. The system handles payment initiation, verification, and sends automated confirmation emails upon successful transactions.

## Features

- **Travel Listings Management**: Browse and view available travel destinations
- **Booking System**: Create bookings with check-in/check-out dates and guest counts
- **Payment Integration**: Secure payment processing via Chapa Payment Gateway
- **Payment Verification**: Automated verification of payment status
- **Email Notifications**: Asynchronous email confirmations using Celery
- **Transaction Tracking**: Complete payment history and status tracking

## Technologies Used

- **Backend Framework**: Django 4.x
- **Database**: PostgreSQL / SQLite
- **Payment Gateway**: Chapa API
- **Task Queue**: Celery with Redis
- **API**: Django REST Framework
- **Environment Management**: python-dotenv

## Project Structure