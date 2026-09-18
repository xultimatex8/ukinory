import { z } from "zod";

const commonPasswords = [
  "password",
  "12345678",
  "123456789",
  "qwerty",
  "qwerty123",
  "1234567890",
  "password123",
  "admin",
  "letmein",
  "welcome",
];

export const profileSchema = z.object({
  username: z
    .string()
    .trim()
    .min(1, "Username is required.")
    .max(150, "Username must be 150 characters or fewer."),

  email: z
    .string()
    .trim()
    .min(1, "Email is required.")
    .email("Enter a valid email address."),
});

export const passwordSchema = z
  .object({
    oldPassword: z
      .string()
      .min(1, "Current password is required."),

    newPassword: z
      .string()
      .min(
        8,
        "This password is too short. It must contain at least 8 characters.",
      )
      .refine(
        (password) => !/^\d+$/.test(password),
        "This password is entirely numeric.",
      )
      .refine(
        (password) => !commonPasswords.includes(password.toLowerCase()),
        "This password is too common.",
      ),

    confirmPassword: z
      .string()
      .min(1, "Please confirm your new password."),
  })
  .superRefine(({ newPassword, confirmPassword }, context) => {
    if (newPassword !== confirmPassword) {
      context.addIssue({
        code: "custom",
        path: ["confirmPassword"],
        message: "Passwords do not match.",
      });
    }
  });

export type ProfileData = z.infer<typeof profileSchema>;
export type PasswordData = z.infer<typeof passwordSchema>;