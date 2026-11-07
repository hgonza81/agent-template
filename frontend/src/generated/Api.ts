/* eslint-disable */
/* tslint:disable */
// @ts-nocheck
/*
 * ---------------------------------------------------------------
 * ## THIS FILE WAS GENERATED VIA SWAGGER-TYPESCRIPT-API        ##
 * ##                                                           ##
 * ## AUTHOR: acacode                                           ##
 * ## SOURCE: https://github.com/acacode/swagger-typescript-api ##
 * ---------------------------------------------------------------
 */

/** ChatMessageRequest */
export interface ChatMessageRequest {
  /**
   * Message
   * @minLength 1
   * @maxLength 4000
   */
  message: string;
}

/** ChatMessageResponse */
export interface ChatMessageResponse {
  /** Reply */
  reply: string;
}

/** ErrorResponse */
export interface ErrorResponse {
  /** Detail */
  detail: string;
  /** Request Id */
  request_id: string;
}

/** SubscriptionResponse */
export interface SubscriptionResponse {
  /** Email */
  email?: string | null;
  /**
   * Id
   * @format uuid
   */
  id: string;
  /**
   * Started At
   * @format date-time
   */
  started_at: string;
}

export namespace Api {
  /**
   * No description
   * @name SendChatMessageApiV1ChatMessagesPost
   * @summary Send Chat Message
   * @request POST:/api/v1/chat/messages
   * @secure
   */
  export namespace SendChatMessageApiV1ChatMessagesPost {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ChatMessageRequest;
    export type RequestHeaders = {};
    export type ResponseBody = ChatMessageResponse;
  }

  /**
   * No description
   * @name HealthLiveApiV1HealthLiveGet
   * @summary Health Live
   * @request GET:/api/v1/health/live
   */
  export namespace HealthLiveApiV1HealthLiveGet {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = Record<string, string>;
  }

  /**
   * No description
   * @name HealthReadyApiV1HealthReadyGet
   * @summary Health Ready
   * @request GET:/api/v1/health/ready
   */
  export namespace HealthReadyApiV1HealthReadyGet {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = Record<string, string>;
  }

  /**
   * No description
   * @name GetMySubscriptionApiV1MeSubscriptionGet
   * @summary Get My Subscription
   * @request GET:/api/v1/me/subscription
   * @secure
   */
  export namespace GetMySubscriptionApiV1MeSubscriptionGet {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = SubscriptionResponse;
  }
}
