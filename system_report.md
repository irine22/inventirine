# Inventory Management System: Functioning Report

## 1. Introduction
The Inventory Management System (IMS) is a high-performance web application built with Python and the Flask framework. It provides a secure and interactive environment for managing product stock, suppliers, and sales transactions.

## 2. System Architecture
The system follows a modular architecture using the **Flask Factory Pattern** and **Blueprints**:
*   **Auth Blueprint**: Handles user registration, login, and profile management.
*   **Inventory Blueprint**: Manages the dashboard, product hubs, and database administrative views.
*   **Database (SQLAlchemy)**: Uses SQLite for efficient, file-based data storage with robust ORM mapping.

## 3. Key Functionalities

### 3.1 Interactive Dashboard
The dashboard uses a "Hub-based" design. Each card (Total Products, Low Stock, Sales) features:
*   **Interactive Toggling**: JavaScript-driven expansion to show hidden details without page reloads.
*   **Real-time Alerts**: Automatic flagging of products with quantity < 10.
*   **Currency Localization**: All financial data is displayed in **France CFA (FCFA)**.

### 3.2 Database Management Hub
A dedicated administrative interface that allows direct interaction with the database tables:
*   **User Management**: View all registered users and their roles.
*   **Inventory Oversight**: Real-time view of product SKUs, prices, and stock levels.

## 4. Security & Data Protection
Security is integrated into every layer of the application:
*   **Authentication**: Secure password hashing using PBKDF2-HMAC-SHA256.
*   **CSRF Protection**: All forms are protected against Cross-Site Request Forgery.
*   **Session Management**: Uses encrypted, HttpOnly session cookies.
*   **Role-Based Access Control (RBAC)**: Normal users are restricted from seeing or accessing administrative hubs.

## 5. User Demonstration
*   **Admin Login**: Access to full system features.
*   **User Registration**: Open registration with automatic role assignment.
*   **Interactive Feedback**: Visual pulses and smooth transitions for all button clicks.

## 6. Conclusion
The system successfully meets all requirements for a secure, professional, and interactive Inventory Management System. It is scalable, role-aware, and provides a premium user experience through its curated "Black and Blue" aesthetic.

---
**Report Prepared for: Bright Favor**
**Status: Fully Operational**
