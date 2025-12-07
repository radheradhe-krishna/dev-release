package com.example.vulnerabilities;

import java.util.List;

public class NotificationService {

    public void sendNotifications(List<String> channels) {
        for (String channel : channels) {
            if (channel == "EMAIL") {
                sendEmail();
            } else if (channel == "SMS") {
                sendSms();
            } else if (channel == "PUSH") {
                sendPush();
            } else {
                System.out.println("Unknown notification channel: " + channel);
            }
        }
    }

    private void sendEmail() {
        System.out.println("Sending email notification...");
    }

    private void sendSms() {
        System.out.println("Sending SMS notification...");
    }

    private void sendPush() {
        System.out.println("Sending push notification...");
    }
}