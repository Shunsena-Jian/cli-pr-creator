/// <reference types="@raycast/api">

/* 🚧 🚧 🚧
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 * 🚧 🚧 🚧 */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {
  /** Projects Directory - The directory where your git repositories are located */
  "projectsDirectory": string
}

/** Preferences accessible in all the extension's commands */
declare type Preferences = ExtensionPreferences

declare namespace Preferences {
  /** Preferences accessible in the `create-pr` command */
  export type CreatePr = ExtensionPreferences & {}
}

declare namespace Arguments {
  /** Arguments passed to the `create-pr` command */
  export type CreatePr = {}
}

